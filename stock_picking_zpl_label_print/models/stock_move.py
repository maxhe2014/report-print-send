from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    def action_open_zpl_label_wizard(self):
        """Open ZPL label printing wizard for selected stock moves"""
        if len(self) == 0:
            raise UserError(_("Please select at least one stock move to print."))
        
        context = {
            'default_move_ids': [(6, 0, self.ids)],
        }
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Print ZPL Labels'),
            'res_model': 'print.picking.zpl.label.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context
        }
    
    def name_get(self):
        """Override name_get to display only product name"""
        result = []
        for move in self:
            # Only display product name if available
            if move.product_id:
                # Use only the product name, no other information
                name = move.product_id.name
            else:
                # Fallback to original behavior if no product
                name = super(StockMove, move).name_get()[0][1]
            result.append((move.id, name))
        return result
