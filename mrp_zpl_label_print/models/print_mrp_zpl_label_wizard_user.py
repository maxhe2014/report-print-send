from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from .base_print_mixin import BasePrintMixin
import logging

_logger = logging.getLogger(__name__)


class PrintMrpZplLabelWizardUser(models.Model, BasePrintMixin):
    _name = 'print.mrp.zpl.label.wizard.user'
    _description = 'User ZPL Label Printer Configuration'
    
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    active = fields.Boolean(string='Active', default=True)
    
    # Simplified printing configuration - only printer selection
    printer_id = fields.Many2one('printing.printer', string='Default Printer', 
                                domain="[('active', '=', True)]",
                                help='Default printer for ZPL label printing')
    
    _sql_constraints = [
        ('user_id_unique', 'UNIQUE(user_id)', 'Each user can only have one default configuration!')
    ]
    
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
        
        # Get product template configuration
        product_template = production.product_id.product_tmpl_id
        
        # Use product template's ZPL configuration if available
        if product_template.zpl_label_template_id:
            label_template = product_template.zpl_label_template_id
            copies_per_label = product_template.zpl_copies_per_label or 1
        else:
            # Fallback to first available ZPL template for stock.lot model
            label_template = self.env['printing.label.zpl2'].search([
                ('model_id.model', '=', 'stock.lot')
            ], limit=1)
            copies_per_label = 1
            
            if not label_template:
                _logger.warning("No ZPL label template found for stock.lot model")
                return False
        
        success_count = 0
        
        # Print each lot record
        for lot in lot_ids:
            try:
                for i in range(copies_per_label):
                    label_template.print_label(printer, lot)
                success_count += 1
            except Exception as e:
                _logger.error(f"Failed to print label for lot {lot.name}: {e}")
        
        _logger.info(f"Successfully printed {success_count} labels for manufacturing order {production.name}")
        return success_count > 0