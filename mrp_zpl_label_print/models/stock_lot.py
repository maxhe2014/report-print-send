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
        """Direct print functionality for stock lots with user preferences support"""
        self.ensure_one()
        
        # Get user's printer from preferences
        user = self.env.user
        printer = user.zpl_printer_id
        
        # Check if user has configured a printer in preferences
        if not printer:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Printing Configuration"),
                    'message': _("Please configure your ZPL label printer in your user preferences (Settings → Users & Companies → Users → Preferences → ZPL Label Printing)."),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Get label template
        label_template = self.env['printing.label.zpl2'].search([
            ('model_id.model', 'in', ['stock.lot', 'mrp.production']),
            ('active', '=', True)
        ], order='name', limit=1)
        
        if not label_template:
            raise UserError(_('No label template found for lots/serial numbers. Please create a label template first.'))
            
        # Print the label
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