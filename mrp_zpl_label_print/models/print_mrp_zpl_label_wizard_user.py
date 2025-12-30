from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from .base_print_mixin import BasePrintMixin
import logging

_logger = logging.getLogger(__name__)


class PrintMrpZplLabelWizardUser(models.Model, BasePrintMixin):
    _name = 'print.mrp.zpl.label.wizard.user'
    _description = 'User Default ZPL Label Printing Configuration'
    
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    active = fields.Boolean(string='Active', default=True)
    
    # Default printing configuration
    label_template_id = fields.Many2one('printing.label.zpl2', string='Default Label Template', 
                                       domain="[('model_id.model', 'in', ['stock.lot', 'mrp.production'])]")
    printer_id = fields.Many2one('printing.printer', string='Default Printer', 
                                domain="[('active', '=', True)]")
    copies_per_label = fields.Integer(string='Default Copies per Label', default=1, 
                                     help='Number of copies to print for each label')
    
    # Trigger conditions
    trigger_mrp_production = fields.Boolean(
        string='Trigger on Manufacturing Production', 
        default=True,
        help='Automatically print labels when manufacturing order is marked as done'
    )
    trigger_repair_order = fields.Boolean(
        string='Trigger on Repair Completion', 
        default=True,
        help='Automatically print labels when repair order is completed'
    )
    trigger_stock_lot = fields.Boolean(
        string='Trigger on Stock Lot/Serial Number', 
        default=False,
        help='Automatically print labels when stock lot/serial number is created or updated'
    )
    
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
            _logger.warning(f"Manufacturing order {production_id} does not exist")
            return False
            
        # 优化：使用prefetch减少数据库查询
        production = production.with_prefetch(self._prefetch)
        
        # Get lots from finished product move lines
        move_lines = production.move_finished_ids.move_line_ids
        lot_ids = move_lines.mapped('lot_id').filtered(lambda l: l)
        if not lot_ids:
            _logger.info(f"Manufacturing order {production.name} has no associated lots/serial numbers")
            return False
        
        # Determine which printer to use
        printer = self.printer_id
        if not printer:
            _logger.warning(f"User {self.user_id.name} has no printer configured")
            return False
            
        if not self.label_template_id:
            _logger.warning(f"User {self.user_id.name} has no label template configured")
            return False
        
        success_count = 0
        # 优化：批量打印处理
        try:
            # 尝试使用批量打印API
            if hasattr(self.label_template_id, 'print_labels_batch'):
                labels_to_print = []
                for lot in lot_ids:
                    for i in range(self.copies_per_label):
                        labels_to_print.append(lot)
                
                if labels_to_print:
                    success_count = self.label_template_id.print_labels_batch(printer, labels_to_print)
            else:
                # 回退到逐条打印，但优化处理
                for lot in lot_ids:
                    try:
                        # 预生成ZPL内容
                        zpl_content = self.label_template_id._generate_zpl_content(lot)
                        for i in range(self.copies_per_label):
                            # 直接发送ZPL内容
                            printer.print_document(
                                None, 
                                zpl_content, 
                                format='raw', 
                                copies=1
                            )
                            success_count += 1
                    except Exception as e:
                        _logger.error(f"Failed to print label for lot {lot.name}: {e}")
        except Exception as e:
            _logger.error(f"Batch printing error for production {production.name}: {e}")
        
        _logger.info(f"Successfully printed {success_count} labels for manufacturing order {production.name}")
        return success_count > 0
    
    def action_auto_print_repair_labels(self, repair_id):
        """Automatically print labels for repair order based on user config"""
        self.ensure_one()
        
        repair = self.env['repair.order'].browse(repair_id)
        if not repair:
            _logger.warning(f"Repair order {repair_id} does not exist")
            return False
            
        # Get lots from repair operations
        lot_ids = repair.move_ids.move_line_ids.lot_id
        if not lot_ids:
            # If no operations with lots, check the main product lot
            if repair.lot_id:
                lot_ids = repair.lot_id
            else:
                _logger.info(f"Repair order {repair.name} has no associated lots/serial numbers")
                return False
        
        # Determine which printer to use
        printer = self.printer_id
        if not printer:
            _logger.warning(f"User {self.user_id.name} has no printer configured")
            return False
            
        if not self.label_template_id:
            _logger.warning(f"User {self.user_id.name} has no label template configured")
            return False
        
        success_count = 0
        # Print each lot
        for lot in lot_ids:
            try:
                for i in range(self.copies_per_label):
                    self.label_template_id.print_label(printer, lot)
                    success_count += 1
            except Exception as e:
                _logger.error(f"Failed to print label for lot {lot.name}: {e}")
        
        _logger.info(f"Successfully printed {success_count} labels for repair order {repair.name}")
        return success_count > 0