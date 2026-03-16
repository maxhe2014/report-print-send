# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PrintRepairZplLabelWizard(models.TransientModel):
    _name = 'print.repair.zpl.label.wizard'
    _description = 'Repair Order ZPL Label Printing Wizard'
    
    repair_id = fields.Many2one(
        comodel_name='repair.order',
        string='Repair Order',
        readonly=True
    )
    
    printer_id = fields.Many2one(
        comodel_name='printing.printer',
        string='Printer',
        compute='_compute_default_printer',
        readonly=True,
        store=False,
        help='Default printer from user preferences'
    )
    
    label_template_id = fields.Many2one(
        comodel_name='printing.label.zpl2',
        string='Label Template',
        required=True,
        domain="[('model_id.model', '=', 'repair.order'), ('active', '=', True)]",
        help='Select the label template to use'
    )
    

    
    copies_per_label = fields.Integer(
        string='Copies per Label',
        default=1,
        help='Number of copies to print for each label'
    )
    
    print_exact_quantity = fields.Boolean(
        string='Print Exact Quantity',
        default=False,
        help='Print exactly the number of copies specified, without multiplying by qty_done'
    )
    
    @api.depends('label_template_id')
    def _compute_default_printer(self):
        """Compute default printer from user preferences or label-user configuration"""
        user = self.env.user
        for wizard in self:
            # 首先尝试获取用户为当前标签模板设置的打印机
            if wizard.label_template_id:
                label_config = self.env['printing.label.zpl2.configuration'].search(
                    [('user_id', '=', user.id), ('label_id', '=', wizard.label_template_id.id)],
                    limit=1
                )
                if label_config and label_config.printer_id:
                    wizard.printer_id = label_config.printer_id
                    continue
            # 如果没有特定配置，使用用户默认ZPL打印机
            wizard.printer_id = user.zpl_printer_id
    
    @api.model
    def default_get(self, fields_list):
        result = super(PrintRepairZplLabelWizard, self).default_get(fields_list)
        
        # Set default repair order
        if self.env.context.get('default_repair_id'):
            repair_id = self.env.context.get('default_repair_id')
            repair = self.env['repair.order'].browse(repair_id)
            if repair.exists():
                result['repair_id'] = repair_id
        
        # Set default label template for repair.order model
        if 'label_template_id' in fields_list and not result.get('label_template_id'):
            user = self.env.user
            # Try to get user's last selected label template for repair.order
            last_template = self.env['printing.label.zpl2.configuration'].search([
                ('user_id', '=', user.id),
                ('label_id.model_id.model', '=', 'repair.order')
            ], order='write_date desc', limit=1)
            if last_template and last_template.label_id:
                result['label_template_id'] = last_template.label_id.id
            else:
                # Fallback to first available repair.order template
                label_template = self.env['printing.label.zpl2'].search([
                    ('model_id.model', '=', 'repair.order'),
                    ('active', '=', True)
                ], order='name', limit=1)
                if label_template:
                    result['label_template_id'] = label_template.id
        
        return result
    
    def action_print_labels(self):
        """Print ZPL labels for the repair order"""
        self.ensure_one()
        
        if not self.printer_id:
            raise UserError(_("No default printer configured. Please set up a default ZPL printer in your user preferences."))
        
        if not self.label_template_id:
            raise UserError(_("Please select a label template."))
        
        try:
            # Determine what to print based on label template model
            template_model = self.label_template_id.model_id.model
            
            if template_model == 'repair.order':
                # Print repair order label
                if not self.repair_id:
                    raise UserError(_("No repair order found to print label for."))
                
                # Calculate total copies
                if self.print_exact_quantity:
                    # Print exactly the number of copies specified
                    total_copies = self.copies_per_label
                else:
                    # Calculate total copies: copies_per_label * repair order product quantity
                    # Use product_qty if available and greater than 0, otherwise use 1
                    product_quantity = self.repair_id.product_qty if hasattr(self.repair_id, 'product_qty') and self.repair_id.product_qty > 0 else 1
                    total_copies = self.copies_per_label * int(product_quantity)
                
                # Print labels one by one to ensure correct quantity
                for i in range(total_copies):
                    self.label_template_id.print_label(
                        self.printer_id,
                        self.repair_id,
                        copies=1
                    )
                
                # Save user's selected label template for future use
                user = self.env.user
                # Check if configuration exists
                label_config = self.env['printing.label.zpl2.configuration'].search([
                    ('user_id', '=', user.id),
                    ('label_id', '=', self.label_template_id.id)
                ], limit=1)
                if not label_config:
                    # Create new configuration
                    self.env['printing.label.zpl2.configuration'].create({
                        'name': f"{user.name}'s {self.label_template_id.name} configuration",
                        'user_id': user.id,
                        'label_id': self.label_template_id.id,
                        'printer_id': self.printer_id.id
                    })
                else:
                    # Update existing configuration
                    label_config.write({
                        'printer_id': self.printer_id.id
                    })
                
                # Show success message
                message = _("Successfully printed %d label(s) for repair order %s.") % (
                    total_copies,
                    self.repair_id.name
                )
            
            else:
                raise UserError(_("Unsupported label template model: %s") % template_model)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"ZPL label printing failed: {e}")
            raise UserError(_("Label printing failed: %s") % str(e))