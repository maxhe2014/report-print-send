from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PrintZplLabelWizard(models.TransientModel):
    _name = 'print.zpl.label.wizard'
    _description = 'ZPL Label Printing Wizard'
    
    printer_id = fields.Many2one(
        comodel_name='printing.printer',
        string='打印机',
        required=True,
        help='选择用于打印标签的打印机'
    )
    
    label_template_id = fields.Many2one(
        comodel_name='printing.label.zpl2',
        string='标签模板',
        required=True,
        domain="[('model_id.model', '=', 'stock.lot'), ('active', '=', True)]",
        help='选择要使用的标签模板'
    )
    
    lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        string='批次/序列号',
        required=True,
        help='选择要打印标签的批次/序列号'
    )
    
    copies_per_label = fields.Integer(
        string='每标签份数',
        default=1,
        help='每个标签打印的份数'
    )
    
    @api.model
    def default_get(self, fields_list):
        result = super(PrintZplLabelWizard, self).default_get(fields_list)
        
        # 设置默认的批次/序列号
        if self.env.context.get('active_ids'):
            result['lot_ids'] = [(6, 0, self.env.context.get('active_ids'))]
        
        # 设置默认打印机：优先使用用户设置的默认ZPL打印机
        user_printer = self.env.user.zpl_printer_id
        if user_printer:
            result['printer_id'] = user_printer.id
        else:
            # 如果没有设置用户默认打印机，则使用系统默认逻辑
            printers = self.env['printing.printer'].search([])
            if len(printers) == 1:
                result['printer_id'] = printers.id
        
        # 设置默认标签模板
        labels = self.env['printing.label.zpl2'].search([
            ('model_id.model', '=', 'stock.lot'),
            ('active', '=', True)
        ], order='name', limit=1)
        if labels:
            result['label_template_id'] = labels.id
        
        return result
    
    def action_print_labels(self):
        """
        执行标签打印
        """
        if not self.lot_ids:
            raise UserError(_('请选择要打印标签的批次/序列号。'))
        
        if not self.printer_id:
            raise UserError(_('请选择打印机。'))
        
        if not self.label_template_id:
            raise UserError(_('请选择标签模板。'))
        
        success_count = 0
        error_messages = []
        
        for lot in self.lot_ids:
            try:
                # 打印指定份数
                for copy in range(self.copies_per_label):
                    self.label_template_id.print_label(self.printer_id, lot)
                success_count += 1
            except Exception as e:
                error_message = _('批次 %s 打印失败: %s') % (lot.name, str(e))
                error_messages.append(error_message)
                _logger.error(error_message)
        
        # 显示结果消息
        message_parts = []
        if success_count > 0:
            message_parts.append(_('成功打印 %d 个标签') % success_count)
        
        if error_messages:
            message_parts.append(_('%d 个标签打印失败') % len(error_messages))
        
        if message_parts:
            message_type = 'warning' if error_messages else 'success'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('打印完成'),
                    'message': '\n'.join(message_parts),
                    'sticky': True,
                    'type': message_type,
                }
            }
        
        return {'type': 'ir.actions.act_window_close'}
    
    def action_test_print(self):
        """
        测试打印功能
        """
        if not self.label_template_id:
            raise UserError(_('请先选择标签模板。'))
        
        if not self.printer_id:
            raise UserError(_('请先选择打印机。'))
        
        # 设置标签模板的测试模式和打印机
        self.label_template_id.write({
            'test_print_mode': True,
            'printer_id': self.printer_id.id
        })
        
        # 执行测试打印
        self.label_template_id.print_test_label()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('测试打印'),
                'message': _('测试打印已发送到打印机'),
                'sticky': False,
                'type': 'success',
            }
        }