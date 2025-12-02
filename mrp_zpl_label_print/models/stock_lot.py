from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockLot(models.Model):
    _inherit = 'stock.lot'
    
    def action_open_print_zpl_label_wizard(self):
        """
        Open the ZPL label printing wizard for flexible label selection
        """
        return {
            'name': _('打印ZPL标签'),
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
        """
        Print using the default label template for quick printing
        """
        # 查找默认的标签模板（按名称排序的第一个）
        label_template = self.env['printing.label.zpl2'].search([
            ('model_id.model', '=', 'stock.lot'),
            ('active', '=', True)
        ], order='name', limit=1)
        
        if not label_template:
            raise UserError(_('未找到适用于批次/序列号的标签模板，请先创建标签模板。'))
        
        # 查找可用的打印机
        printer = self.env['printing.printer'].search([], limit=1)
        if not printer:
            raise UserError(_('未找到可用的打印机，请先配置打印机。'))
        
        # 为每个选中的批次/序列号打印标签
        success_count = 0
        for lot in self:
            try:
                label_template.print_label(printer, lot)
                success_count += 1
            except Exception as e:
                _logger.error(f"打印标签失败: {e}")
        
        # 显示成功消息
        if success_count > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('打印成功'),
                    'message': _('已成功打印 %d 个标签') % success_count,
                    'sticky': False,
                    'type': 'success',
                }
            }
        else:
            raise UserError(_('打印失败，请检查打印机配置和标签模板。'))