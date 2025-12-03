from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class PrintMrpZplLabelWizard(models.TransientModel):
    _name = 'print.mrp.zpl.label.wizard'
    _description = 'Print ZPL Labels for Manufacturing Order'

    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', required=True)
    printer_id = fields.Many2one('printing.printer', string='Printer', required=True,
                                domain="[('id', 'in', available_printer_ids)]")
    label_template_id = fields.Many2one('printing.label.zpl2', string='Label Template', required=True,
                                       domain="[('model_id.model', '=', 'stock.lot')]")
    lot_ids = fields.Many2many('stock.lot', string='Lots/Serials',
                              domain="[('id', 'in', available_lot_ids)]")
    copies_per_label = fields.Integer(string='Copies per Label', default=1,
                                     help='Number of copies to print for each label')
    
    # Available printers and lots
    available_printer_ids = fields.Many2many('printing.printer', compute='_compute_available_printers')
    available_lot_ids = fields.Many2many('stock.lot', compute='_compute_available_lots')
    
    @api.constrains('copies_per_label')
    def _check_copies_per_label(self):
        """Validate copies per label value"""
        for record in self:
            if record.copies_per_label < 1 or record.copies_per_label > 10:
                raise ValidationError(_('Copies per label must be between 1 and 10.'))

    @api.depends('production_id')
    def _compute_available_lots(self):
        for wizard in self:
            if wizard.production_id:
                # Get lots from finished product move lines
                lot_ids = wizard.production_id.move_finished_ids.mapped('move_line_ids.lot_id').ids
                wizard.available_lot_ids = [(6, 0, lot_ids)]
                # Set default lots if not set
                if not wizard.lot_ids and lot_ids:
                    wizard.lot_ids = [(6, 0, lot_ids)]
            else:
                wizard.available_lot_ids = False

    @api.depends('printer_id')
    def _compute_available_printers(self):
        """Compute available printers for ZPL printing."""
        for wizard in self:
            # Search for all active printers
            printers = self.env['printing.printer'].search([('active', '=', True)])
            wizard.available_printer_ids = printers

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Get context values
        production_id = self.env.context.get('default_production_id')
        lot_ids = self.env.context.get('default_lot_ids')
        
        if production_id:
            res['production_id'] = production_id
            
            # Set default lots from context
            if lot_ids:
                res['lot_ids'] = lot_ids
            
            # Set default label template
            label_template = self.env['printing.label.zpl2'].search([
                ('model_id.model', '=', 'stock.lot')
            ], limit=1)
            if label_template:
                res['label_template_id'] = label_template.id
        
        # Multi-level printer selection priority:
        # 1. User's default ZPL printer (new field)
        # 2. User's default printer (original field)
        # 3. First active printer
        
        if self.env.user.zpl_printer_id:
            # Priority 1: User's default ZPL printer (new field)
            res['printer_id'] = self.env.user.zpl_printer_id.id
        elif self.env.user.printing_printer_id:
            # Priority 2: User's default printer (original field)
            res['printer_id'] = self.env.user.printing_printer_id.id
        else:
            # Priority 3: First active printer
            printer = self.env['printing.printer'].search([('active', '=', True)], limit=1)
            if printer:
                res['printer_id'] = printer.id
            
        return res

    def action_print_labels(self):
        """Print ZPL labels for selected lots"""
        self.ensure_one()
        
        if not self.lot_ids:
            raise ValidationError(_("请选择至少一个批次/序列号进行打印。"))
        
        if not self.printer_id:
            raise ValidationError(_("请选择打印机。"))
            
        if not self.label_template_id:
            raise ValidationError(_("请选择标签模板。"))
        
        success_count = 0
        error_messages = []
        
        # Print each lot
        for lot in self.lot_ids:
            try:
                for i in range(self.copies_per_label):
                    self.label_template_id.print_label(self.printer_id, lot)
                    success_count += 1
            except Exception as e:
                error_msg = f"批次 {lot.name} 打印失败: {str(e)}"
                error_messages.append(error_msg)
                _logger.error(error_msg)
        
        # Show result message
        if success_count > 0:
            message = _("成功打印了 %d 个标签") % success_count
            if error_messages:
                message += _("，但有 %d 个标签打印失败") % len(error_messages)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('打印结果'),
                    'message': message,
                    'sticky': False,
                    'type': 'success' if not error_messages else 'warning',
                }
            }
        else:
            raise UserError(_("所有标签打印失败，请检查打印机配置和网络连接。\n错误信息: %s") % '\n'.join(error_messages))
        
        return {'type': 'ir.actions.act_window_close'}

    def action_test_print(self):
        """Test print functionality"""
        self.ensure_one()
        
        if not self.lot_ids:
            raise models.ValidationError("Please select at least one lot to test print.")
        
        # Test print the first lot
        test_lot = self.lot_ids[0]
        
        # Create test content
        test_content = f"TEST PRINT - {test_lot.name}"
        
        # Send test print
        self.printer_id.print_document(
            None, 
            test_content, 
            format='raw', 
            copies=1
        )
        
        return {'type': 'ir.actions.act_window_close'}