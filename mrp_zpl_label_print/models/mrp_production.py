from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def button_mark_done(self):
        """Override the mark as done button to automatically print labels with priority:
        1. Product-level ZPL configuration (highest priority)
        2. User-level ZPL configuration (fallback)"""
        result = super().button_mark_done()
        
        # Handle batch operations by iterating through each manufacturing order
        for mo in self:
            try:
                # Get lots from finished product move lines
                lot_ids = mo.move_finished_ids.mapped('move_line_ids.lot_id')
                if not lot_ids:
                    continue
                
                # Priority 1: Check product-level ZPL configuration
                product_template = mo.product_id.product_tmpl_id
                if product_template.zpl_label_template_id:
                    # Product has ZPL configuration, use it
                    mo._print_labels_with_product_config(product_template, lot_ids)
                    continue
                
                # Priority 2: Check user-level ZPL configuration (fallback)
                user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
                if user_config and user_config.active and user_config.label_template_id and user_config.trigger_mrp_production:
                    # Use user configuration only if trigger is enabled
                    user_config.action_auto_print_labels(mo.id)
            except Exception as e:
                _logger.error(f"Automatic ZPL label printing failed (Manufacturing Order {mo.name}): {e}")
                # Do not interrupt the normal flow, only log the error
        
        return result
    
    def _print_labels_with_product_config(self, product_template, lot_ids):
        """Print labels using product-level ZPL configuration"""
        # Printer selection: ALWAYS use user configuration (regardless of product config)
        user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
        if user_config and user_config.active and user_config.printer_id:
            printer = user_config.printer_id
        else:
            # Fallback to user's default printer or first active printer
            printer = self._get_printer_with_fallback()
        
        if not printer:
            # No printer available, skip printing
            _logger.warning(f"No printer available for ZPL label printing (Product: {product_template.name})")
            return
        
        # Print each lot with product configuration
        label_template = product_template.zpl_label_template_id
        
        # Determine copies per label: if product has specific value, use it; otherwise use user config or default
        if product_template.zpl_copies_per_label is not None and product_template.zpl_copies_per_label is not False:
            copies_per_label = product_template.zpl_copies_per_label
        else:
            # Fallback to user configuration
            if user_config and user_config.active and user_config.copies_per_label:
                copies_per_label = user_config.copies_per_label
            else:
                copies_per_label = 1
        
        for lot in lot_ids:
            for i in range(copies_per_label):
                label_template.print_label(printer, lot)
    
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
        
        # Priority 1: Check product-level ZPL configuration
        product_template = self.product_id.product_tmpl_id
        if product_template.zpl_label_template_id:
            # Product has ZPL configuration, use it
            return self._print_labels_with_product_config_direct(product_template, lot_ids)
        
        # Priority 2: Check user-level ZPL configuration (fallback)
        user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
        if not user_config or not user_config.active:
            raise UserError(_('No active user configuration found for ZPL label printing.'))
        
        # Determine printer to use
        printer = user_config.printer_id
        if not printer:
            raise UserError(_('No printer configured for ZPL label printing.'))
            
        if not user_config.label_template_id:
            raise UserError(_('No label template configured for ZPL label printing.'))
        
        # Print labels
        success_count = 0
        error_messages = []
        
        for lot in lot_ids:
            try:
                # Print specified number of copies
                for i in range(user_config.copies_per_label):
                    user_config.label_template_id.print_label(printer, lot)
                success_count += 1
            except Exception as e:
                error_message = _('Failed to print label for lot %s: %s') % (lot.name, str(e))
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
                    'message': '\n'.join(message_parts),
                    'sticky': True,
                    'type': message_type,
                }
            }
        
        return {'type': 'ir.actions.act_window_close'}
    
    def _print_labels_with_product_config_direct(self, product_template, lot_ids):
        """Print labels using product-level ZPL configuration (direct action)"""
        # Printer selection: ALWAYS use user configuration (regardless of product config)
        user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
        if user_config and user_config.active and user_config.printer_id:
            printer = user_config.printer_id
        else:
            # Fallback to user's default printer or first active printer
            printer = self._get_printer_with_fallback()
        
        if not printer:
            raise UserError(_('No printer available for ZPL label printing.'))
        
        # Print each lot with product configuration
        label_template = product_template.zpl_label_template_id
        
        # Determine copies per label: if product has specific value, use it; otherwise use user config or default
        if product_template.zpl_copies_per_label is not None and product_template.zpl_copies_per_label is not False:
            copies_per_label = product_template.zpl_copies_per_label
        else:
            # Fallback to user configuration
            if user_config and user_config.active and user_config.copies_per_label:
                copies_per_label = user_config.copies_per_label
            else:
                copies_per_label = 1
        
        success_count = 0
        error_messages = []
        
        for lot in lot_ids:
            try:
                for i in range(copies_per_label):
                    label_template.print_label(printer, lot)
                success_count += 1
            except Exception as e:
                error_message = _('Failed to print label for lot %s: %s') % (lot.name, str(e))
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
                    'message': '\n'.join(message_parts),
                    'sticky': True,
                    'type': message_type,
                }
            }
        
        return {'type': 'ir.actions.act_window_close'}