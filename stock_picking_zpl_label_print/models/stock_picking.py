from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    def action_open_zpl_label_wizard(self):
        """Open ZPL label printing wizard for the current picking"""
        self.ensure_one()
        
        # Get lots from the picking (if any)
        lot_ids = self.move_line_ids.mapped('lot_id').ids
        
        # Open the wizard even if no lots found
        # User can choose to print picking label or wait for lots to be available
        context = {
            'default_picking_id': self.id,
            'default_lot_ids': [(6, 0, lot_ids)] if lot_ids else False,
        }
        
        if lot_ids:
            context['active_ids'] = lot_ids
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Print ZPL Labels'),
            'res_model': 'print.picking.zpl.label.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context
        }