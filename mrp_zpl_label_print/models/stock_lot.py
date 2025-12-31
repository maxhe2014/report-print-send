from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .base_print_mixin import BasePrintMixin
import logging

_logger = logging.getLogger(__name__)

class StockLot(models.Model, BasePrintMixin):
    _inherit = 'stock.lot'
    
    def action_open_print_zpl_label_wizard(self):
        """
        Open the ZPL label printing wizard for flexible label selection
        """
        return {
            'name': _('Print ZPL Label'),
            'type': 'ir.actions.act_window',
            'res_model': 'print.zpl.label.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_ids': [(6, 0, self.ids)],
                'active_model': 'stock.lot',
                'active_ids': self.ids,
                'active_id': self.id if len(self) == 1 else False,
            }
        }
    
    def action_print_default_zpl_label(self):
        """Direct print functionality for stock lots with user configuration support"""
        self.ensure_one()
        
        # Get user's default configuration
        user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
        
        # Check if user configuration is complete
        if user_config and not (user_config.active and user_config.printer_id):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Printing Configuration"),
                    'message': _("Your ZPL label printing configuration is incomplete. Please configure an active printer."),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Get user's default settings or fall back to system defaults
        if user_config and user_config.label_template_id and user_config.printer_id:
            label_template = user_config.label_template_id
            printer = user_config.printer_id
            copies = user_config.copies_per_label or 1
        else:
            # Fall back to system defaults
            label_template = self.env['printing.label.zpl2'].search([
                ('model_id.model', 'in', ['stock.lot', 'mrp.production']),
                ('active', '=', True)
            ], order='name', limit=1)
            
            if not label_template:
                raise UserError(_('No label template found for lots/serial numbers. Please create a label template first.'))
                
            printer = self._get_printer_with_fallback()
            copies = 1
            
        if not printer:
            raise UserError(_('No printer found. Please configure a printer first.'))
            
        # Print the label (possibly multiple copies)
        for i in range(copies):
            label_template.print_label(printer, self)
        
        # Return success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Success"),
                'message': _("Label printed successfully"),
                'type': 'success',
                'sticky': False,
            }
        }