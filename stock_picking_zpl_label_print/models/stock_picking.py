from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    def action_open_zpl_label_wizard(self):
        """Open ZPL label printing wizard for the current picking"""
        self.ensure_one()
        
        # Open the wizard with the current picking
        context = {
            'default_picking_id': self.id,
        }
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Print ZPL Labels'),
            'res_model': 'print.picking.zpl.label.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context
        }