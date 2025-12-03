from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class PrintMrpZplLabelWizardUser(models.Model):
    _name = 'print.mrp.zpl.label.wizard.user'
    _description = 'User Default ZPL Label Printing Configuration'
    
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    active = fields.Boolean(string='Active', default=True)
    
    # Default printing configuration
    label_template_id = fields.Many2one('printing.label.zpl2', string='Default Label Template', 
                                       domain="[('model_id.model', '=', 'stock.lot')]")
    printer_id = fields.Many2one('printing.printer', string='Default Printer', 
                                domain="[('active', '=', True)]")
    copies_per_label = fields.Integer(string='Default Copies per Label', default=1, 
                                     help='Number of copies to print for each label')
    
    _sql_constraints = [
        ('user_id_unique', 'UNIQUE(user_id)', 'Each user can only have one default configuration!')
    ]
    
    @api.constrains('copies_per_label')
    def _check_copies_per_label(self):
        """Validate copies per label value"""
        for record in self:
            if record.copies_per_label < 1 or record.copies_per_label > 10:
                raise ValidationError(_('Copies per label must be between 1 and 10.'))
    
    @api.model
    def get_user_config(self, user_id=None):
        """Get user's default printing configuration"""
        if user_id is None:
            user_id = self.env.user.id
            
        config = self.search([
            ('user_id', '=', user_id),
            ('active', '=', True)
        ], limit=1)
        
        return config
    
    def action_auto_print_labels(self, production_id):
        """Automatically print labels for manufacturing order based on user config"""
        self.ensure_one()
        
        production = self.env['mrp.production'].browse(production_id)
        if not production:
            _logger.warning(f"制造订单 {production_id} 不存在")
            return False
            
        # Get lots from finished product move lines
        lot_ids = production.move_finished_ids.mapped('move_line_ids.lot_id')
        if not lot_ids:
            _logger.info(f"制造订单 {production.name} 没有关联的批次/序列号")
            return False
        
        # Determine which printer to use
        printer = self.printer_id
        if not printer:
            # Fallback to user's default ZPL printer
            printer = self.user_id.zpl_printer_id
        
        if not printer:
            _logger.warning(f"用户 {self.user_id.name} 没有配置打印机")
            return False
            
        if not self.label_template_id:
            _logger.warning(f"用户 {self.user_id.name} 没有配置标签模板")
            return False
        
        success_count = 0
        # Print each lot
        for lot in lot_ids:
            try:
                for i in range(self.copies_per_label):
                    self.label_template_id.print_label(printer, lot)
                    success_count += 1
            except Exception as e:
                _logger.error(f"打印批次 {lot.name} 的标签失败: {e}")
        
        _logger.info(f"成功为制造订单 {production.name} 打印了 {success_count} 个标签")
        return success_count > 0