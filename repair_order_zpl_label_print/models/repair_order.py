# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class RepairOrder(models.Model):
    _inherit = 'repair.order'
    

    
    def action_open_zpl_label_wizard(self):
        """Open the ZPL label printing wizard for repair order"""
        self.ensure_one()
        
        return {
            'name': _('Print ZPL Labels'),
            'type': 'ir.actions.act_window',
            'res_model': 'print.repair.zpl.label.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_repair_id': self.id,
            },
        }