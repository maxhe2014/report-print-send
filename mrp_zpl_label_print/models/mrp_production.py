from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def button_mark_done(self):
        """Override the mark as done button to automatically print labels with priority:
        Only print when both product-level ZPL configuration AND user-level printer configuration are complete.
        If either is missing, skip printing."""
        result = super().button_mark_done()
        
        # Handle batch operations by iterating through each manufacturing order
        for mo in self:
            try:
                # Get lots from finished product move lines
                lot_ids = mo.move_finished_ids.mapped('move_line_ids.lot_id')
                if not lot_ids:
                    continue
                
                # Check both configurations: product-level AND user-level
                product_template = mo.product_id.product_tmpl_id
                user = self.env.user
                
                # Only proceed if BOTH configurations are complete
                has_product_config = bool(product_template.zpl_label_template_id)
                has_user_config = bool(user.zpl_printer_id)
                
                if not has_product_config or not has_user_config:
                    # Skip printing if either configuration is missing
                    missing_configs = []
                    if not has_product_config:
                        missing_configs.append("product-level label template")
                    if not has_user_config:
                        missing_configs.append("user-level printer configuration")
                    
                    _logger.info(f"Skipping automatic ZPL label printing for MO {mo.name}: Missing {', '.join(missing_configs)}")
                    continue
                
                # Both configurations are complete, proceed with printing
                # Priority: Use product-level ZPL configuration
                mo._print_labels_with_product_config(product_template, lot_ids)
                    
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
            _logger.warning(f"No ZPL printer configured in user preferences for user: {user.name}")
            return
            
        # Get label template for stock.lot model
        label_template = self.env['printing.label.zpl2'].search([
            ('model_id.model', '=', 'stock.lot'),
            ('active', '=', True)
        ], order='name', limit=1)
        
        if not label_template:
            _logger.warning("No label template found for stock.lot model")
            return
        
        # Print each lot record
        for lot in lot_ids:
            try:
                label_template.print_label(printer, lot)
            except Exception as e:
                _logger.error(f"Failed to print label for lot {lot.name}: {e}")
    
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
            _logger.warning(f"No printer available for ZPL label printing (Product: {product_template.name})")
            return
        
        # Use specific manufacturing template only
        label_template = product_template.zpl_label_template_id
        
        if not label_template:
            _logger.warning(f"Product {product_template.name} has no manufacturing order label template configured")
            return
        
        # Determine copies per label: use product configuration if available, otherwise default to 1
        copies_per_label = product_template.zpl_copies_per_label or 1
        
        # Determine which records to print based on label template model
        label_template_model = label_template.model_id.model
        
        if label_template_model == 'stock.lot':
            # Print each lot record
            for lot in lot_ids:
                for i in range(copies_per_label):
                    label_template.print_label(printer, lot)
        elif label_template_model == 'mrp.production':
            # Print the manufacturing order record itself
            for i in range(copies_per_label):
                label_template.print_label(printer, self)
        else:
            _logger.warning(f'Unsupported label template model: {label_template_model}')
    
    def _get_printer_with_fallback(self):
        """Get printer with fallback logic: user default printer -> first active printer"""
        # Priority 1: User's default printer
        if self.env.user.printing_printer_id:
            return self.env.user.printing_printer_id
        
        # Priority 2: First active printer
        printer = self.env['printing.printer'].search([('active', '=', True)], limit=1)
        return printer

    def action_open_mrp_zpl_label_wizard(self):
        """Directly print ZPL labels for manufacturing orders without wizard"""
        self.ensure_one()
        
        # Get lots from finished product move lines
        lot_ids = self.move_finished_ids.mapped('move_line_ids.lot_id')
        if not lot_ids:
            raise UserError(_('No lots/serial numbers found for this manufacturing order.'))
        
        # Check if both product-level and user-level configurations are complete
        product_template = self.product_id.product_tmpl_id
        user = self.env.user
        
        # Check product-level configuration
        has_product_config = bool(product_template.zpl_label_template_id)
        
        # Check user-level configuration
        has_user_config = bool(user.zpl_printer_id)
        
        # Both configurations must be complete to proceed with printing
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
        
        # Both configurations are complete, proceed with printing
        # Priority 1: Use product-level ZPL configuration
        if has_product_config:
            return self._print_labels_with_product_config_direct(product_template, lot_ids)
        
        # This point should not be reached due to the checks above
        return {'type': 'ir.actions.act_window_close'}
    
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
        copies_per_label = product_template.zpl_copies_per_label or 1
        
        # Determine which records to print based on label template model
        label_template_model = label_template.model_id.model
        
        success_count = 0
        error_messages = []
        
        if label_template_model == 'stock.lot':
            # Print each lot record
            for lot in lot_ids:
                try:
                    for i in range(copies_per_label):
                        label_template.print_label(printer, lot)
                    success_count += 1
                except Exception as e:
                    error_message = _('Failed to print label for lot %s: %s') % (lot.name, str(e))
                    error_messages.append(error_message)
                    _logger.error(error_message)
        elif label_template_model == 'mrp.production':
            # Print the manufacturing order record itself
            try:
                for i in range(copies_per_label):
                    label_template.print_label(printer, self)
                success_count += 1
            except Exception as e:
                error_message = _('Failed to print label for manufacturing order %s: %s') % (self.name, str(e))
                error_messages.append(error_message)
                _logger.error(error_message)
        else:
            error_message = _('Unsupported label template model: %s') % label_template_model
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