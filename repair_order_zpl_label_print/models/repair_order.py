# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class RepairOrder(models.Model):
    _inherit = 'repair.order'
    
    move_line_ids = fields.Many2many('stock.move.line', compute='_compute_move_line_ids', string='Stock Move Lines')
    
    def _compute_move_line_ids(self):
        for repair in self:
            # 获取与维修订单相关的库存移动行
            move_lines = self.env['stock.move.line'].search([
                ('reference', '=', repair.name),
                ('state', '!=', 'cancel')
            ])
            repair.move_line_ids = move_lines
    
    def action_open_zpl_label_wizard(self):
        """Open the ZPL label printing wizard for repair order"""
        self.ensure_one()
        
        # Get stock move lines from the repair order
        move_line_ids = self.move_line_ids.filtered(lambda m: m.state != 'cancel').ids
        
        return {
            'name': _('Print ZPL Labels'),
            'type': 'ir.actions.act_window',
            'res_model': 'print.repair.zpl.label.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_repair_id': self.id,
                'default_move_line_ids': [(6, 0, move_line_ids)],
            },
        }