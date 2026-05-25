from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .base_print_mixin import BasePrintMixin
import logging
import time

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model, BasePrintMixin):
    _inherit = 'mrp.production'
    
    # Class-level cache to track printed MOs across function calls
    # Format: {mo_id: timestamp}
    _zpl_printed_mo_cache = {}
    # Cache cleanup threshold (seconds) - clean up entries older than 5 minutes
    _ZPL_CACHE_CLEANUP_THRESHOLD = 300

    def _cleanup_zpl_cache(self):
        """Clean up old entries from the ZPL print cache"""
        now = time.time()
        expired_ids = [
            mo_id for mo_id, timestamp in MrpProduction._zpl_printed_mo_cache.items()
            if now - timestamp > MrpProduction._ZPL_CACHE_CLEANUP_THRESHOLD
        ]
        for mo_id in expired_ids:
            del MrpProduction._zpl_printed_mo_cache[mo_id]

    def button_mark_done(self):
        """Override the mark as done button to automatically print labels with priority:
        Only print when both product-level ZPL configuration AND user-level printer configuration are complete.
        If either is missing, skip printing."""
        result = super().button_mark_done()
        
        # Clean up cache periodically to prevent memory leaks
        self._cleanup_zpl_cache()
        
        # Handle batch operations by iterating through each manufacturing order
        for mo in self:
            try:
                # Skip if already printed (using class-level cache to prevent duplicate printing)
                if mo.id in MrpProduction._zpl_printed_mo_cache:
                    _logger.info(f"[ZPL PRINT] MO {mo.name} - Skipping (already printed in this session)")
                    continue
                
                # Re-fetch the manufacturing order to get the latest move_finished_ids
                mo = self.env['mrp.production'].browse(mo.id)
                
                # Get lots from finished product move lines
                lot_ids = mo.move_finished_ids.mapped('move_line_ids.lot_id')
                
                # Remove duplicates - same lot may appear in multiple move lines
                seen = set()
                unique_lot_ids = []
                for lot in lot_ids:
                    if lot.id not in seen:
                        seen.add(lot.id)
                        unique_lot_ids.append(lot.id)
                lot_ids = self.env['stock.lot'].browse(unique_lot_ids)
                
                # Check both configurations: product-level AND user-level
                product_template = mo.product_id.product_tmpl_id
                user = self.env.user
                
                # Only proceed if BOTH configurations are complete
                has_product_config = bool(product_template.zpl_label_template_id)
                has_user_config = bool(user.zpl_printer_id)
                
                if not has_product_config or not has_user_config:
                    # Skip printing if either configuration is missing
                    continue
                
                # Both configurations are complete, proceed with printing
                # Priority: Use product-level ZPL configuration
                mo._print_labels_with_product_config(product_template, lot_ids)
                
                # Mark as printed in class-level cache with timestamp
                MrpProduction._zpl_printed_mo_cache[mo.id] = time.time()
                    
            except Exception as e:
                _logger.error(f"Automatic ZPL label printing failed (Manufacturing Order {mo.name}): {e}")
                # Do not interrupt the normal flow, only log the error
        
        return result
    
    def _print_labels_with_user_preferences(self, lot_ids):
        """Print labels using user preferences configuration"""
        user = self.env.user
        printer = user.zpl_printer_id
        
        if not printer:
            # No printer available, skip printing
            return
            
        # Get label template for stock.lot model
        label_template = self.env['printing.label.zpl2'].search([
            ('model_id.model', '=', 'stock.lot'),
            ('active', '=', True)
        ], order='name', limit=1)
        
        if not label_template:
            return
        
        # Print each lot record
        for lot in lot_ids:
            try:
                label_template.print_label(printer, lot)
            except Exception:
                pass
    
    def _print_labels_with_product_config(self, product_template, lot_ids):
        """Print labels using product-level ZPL configuration"""
        # Printer selection: ALWAYS use user preferences (regardless of product config)
        user = self.env.user
        printer = user.zpl_printer_id
        
        if not printer:
            # Fallback to user's default printer or first active printer
            printer = self._get_printer_with_fallback()
        
        if not printer:
            # No printer available, skip printing
            return
        
        # Use specific manufacturing template only
        label_template = product_template.zpl_label_template_id
        
        if not label_template:
            return
        
        # Determine copies per label: use product configuration if available, otherwise default to 1
        base_copies = product_template.zpl_copies_per_label or 1
        
        # Multiply by production quantity only for mrp.production template
        # For stock.lot template, each lot represents one product unit, so no need to multiply
        production_qty = self.product_qty
        label_template_model = label_template.model_id.model
        if label_template_model == 'mrp.production':
            copies_per_label = int(base_copies * production_qty)
        else:
            copies_per_label = int(base_copies)
        
        # Use common print method
        if label_template_model == 'stock.lot':
            self._print_labels(
                printer=printer,
                label_template=label_template,
                records=lot_ids,
                copies_per_label=copies_per_label
            )
        elif label_template_model == 'mrp.production':
            self._print_labels(
                printer=printer,
                label_template=label_template,
                records=self,
                copies_per_label=copies_per_label
            )
    


    def action_open_mrp_zpl_label_wizard(self):
        """Open ZPL label printing wizard for manufacturing orders"""
        self.ensure_one()
        
        # Get lots from all move lines (both raw materials and finished products)
        # This allows printing labels even before the manufacturing order is completed
        move_lines = self.move_raw_ids.mapped('move_line_ids') + self.move_finished_ids.mapped('move_line_ids')
        lot_ids = move_lines.mapped('lot_id').filtered(lambda l: l)
        
        # Don't raise error if no lots found, as we can still print using mrp.production template
        # The wizard will handle the case based on the selected template model
        
        # Open the ZPL label printing wizard
        return {
            'name': _('Print ZPL Labels'),
            'type': 'ir.actions.act_window',
            'res_model': 'print.mrp.zpl.label.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_id': self.id,
                'default_lot_ids': [(6, 0, lot_ids.ids)],
                'active_model': 'mrp.production',
                'active_ids': self.ids,
                'active_id': self.id,
            }
        }
    
    def action_print_zpl_direct(self):
        """Directly print ZPL labels for manufacturing orders"""
        self.ensure_one()
        
        # Get lots from finished product move lines
        lot_ids = self.move_finished_ids.mapped('move_line_ids.lot_id')
        
        # Remove duplicates - same lot may appear in multiple move lines
        seen = set()
        unique_lot_ids = []
        for lot in lot_ids:
            if lot.id not in seen:
                seen.add(lot.id)
                unique_lot_ids.append(lot.id)
        lot_ids = self.env['stock.lot'].browse(unique_lot_ids)
        
        if not lot_ids:
            raise UserError(_('No lots/serial numbers found for this manufacturing order.'))
        
        # Check configurations
        product_template = self.product_id.product_tmpl_id
        user = self.env.user
        
        # Check product-level configuration
        has_product_config = bool(product_template.zpl_label_template_id)
        
        # Check user-level configuration
        has_user_config = bool(user.zpl_printer_id)
        
        # Validate configurations
        config_error = self._validate_print_configurations(has_product_config, has_user_config)
        if config_error:
            return config_error
        
        # Both configurations are complete, proceed with printing
        # Priority 1: Use product-level ZPL configuration
        if has_product_config:
            return self._print_labels_with_product_config_direct(product_template, lot_ids)
        
        # This point should not be reached due to the checks above
        return {'type': 'ir.actions.act_window_close'}
    
    def _validate_print_configurations(self, has_product_config, has_user_config):
        """Validate print configurations and return error message if any
        
        Args:
            has_product_config: bool - whether product has ZPL configuration
            has_user_config: bool - whether user has ZPL printer configuration
            
        Returns:
            dict or None: error message action if validation fails, None otherwise
        """
        if not has_product_config and not has_user_config:
            # Neither configuration is complete
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Print Labels'),
                    'message': _('No ZPL label printing configuration found. Please configure either product-level or user-level printing settings.'),
                    'sticky': False,
                    'type': 'info',
                }
            }
        elif not has_product_config:
            # Product configuration is missing but user configuration exists
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Print Labels'),
                    'message': _('No label template configured for this product. Please configure the product-level ZPL label template.'),
                    'sticky': False,
                    'type': 'info',
                }
            }
        elif not has_user_config:
            # User configuration is missing but product configuration exists
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Print Labels'),
                    'message': _('No ZPL printer configured. Please configure your ZPL label printer in your user preferences (Settings → Users & Companies → Users → Preferences → ZPL Label Printing).'),
                    'sticky': False,
                    'type': 'info',
                }
            }
        
        return None
    
    def _print_labels_with_product_config_direct(self, product_template, lot_ids):
        """Print labels using product-level ZPL configuration (direct action)"""
        # Printer selection: ALWAYS use user preferences (regardless of product config)
        user = self.env.user
        printer = user.zpl_printer_id
        
        if not printer:
            # Fallback to user's default printer or first active printer
            printer = self._get_printer_with_fallback()
        
        if not printer:
            # No printer available, show info message and return
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Print Labels'),
                    'message': _('No printer available for ZPL label printing.'),
                    'sticky': False,
                    'type': 'info',
                }
            }
        
        # Use specific manufacturing template only
        label_template = product_template.zpl_label_template_id
        
        if not label_template:
            # No template configured for this product, show info message and return
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Print Labels'),
                    'message': _('No manufacturing order label template configured for this product.'),
                    'sticky': False,
                    'type': 'info',
                }
            }
        
        # Determine copies per label: use product configuration if available, otherwise default to 1
        # For direct print from list view, do not multiply by production quantity
        copies_per_label = int(product_template.zpl_copies_per_label or 1)
        
        # Determine which records to print based on label template model
        label_template_model = label_template.model_id.model
        
        success_count = 0
        error_messages = []
        
        # 批量生成ZPL数据
        zpl_content = b""
        
        if label_template_model == 'stock.lot':
            # 批量生成标签数据
            for lot in lot_ids:
                try:
                    for i in range(copies_per_label):
                        # 生成单个标签的ZPL数据
                        label_content = label_template._generate_zpl2_data(lot)
                        zpl_content += label_content
                    success_count += 1
                except Exception as e:
                    error_message = _('Failed to generate label for lot %s: %s') % (lot.name, str(e))
                    error_messages.append(error_message)
                    _logger.error(error_message)
        elif label_template_model == 'mrp.production':
            # 批量生成标签数据
            try:
                for i in range(copies_per_label):
                    label_content = label_template._generate_zpl2_data(self)
                    zpl_content += label_content
                success_count += 1
            except Exception as e:
                error_message = _('Failed to generate label for manufacturing order %s: %s') % (self.name, str(e))
                error_messages.append(error_message)
                _logger.error(error_message)
        else:
            error_message = _('Unsupported label template model: %s') % label_template_model
            error_messages.append(error_message)
            _logger.error(error_message)
        
        # 一次性发送所有标签
        if zpl_content:
            try:
                printer.print_document(None, zpl_content, format='raw')
            except Exception as e:
                error_message = _('Failed to send print job: %s') % str(e)
                error_messages.append(error_message)
                _logger.error(error_message)
        
        # Show result notification
        message_parts = []
        if success_count > 0:
            message_parts.append(_('Successfully printed %d labels') % success_count)
        
        if error_messages:
            message_parts.append(_('%d labels failed to print') % len(error_messages))
        
        if message_parts:
            message_type = 'warning' if error_messages else 'success'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Print Labels'),
                    'message': '\\n'.join(message_parts),
                    'sticky': True,
                    'type': message_type,
                }
            }
        
        return {'type': 'ir.actions.act_window_close'}