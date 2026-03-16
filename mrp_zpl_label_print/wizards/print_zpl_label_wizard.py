from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..models.base_print_mixin import BasePrintMixin
import logging

_logger = logging.getLogger(__name__)

class PrintZplLabelWizard(models.TransientModel, BasePrintMixin):
    _name = 'print.zpl.label.wizard'
    _description = 'ZPL Label Printing Wizard'
    
    printer_id = fields.Many2one(
        comodel_name='printing.printer',
        string='Printer',
        required=True,
        help='Select the printer to use for printing labels'
    )
    
    label_template_id = fields.Many2one(
        comodel_name='printing.label.zpl2',
        string='Label Template',
        required=True,
        domain="[('model_id.model', '=', 'stock.lot'), ('active', '=', True)]",
        help='Select the label template to use'
    )
    
    lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        string='Lots/Serial Numbers',
        required=True,
        help='Select the lots/serial numbers to print labels for'
    )
    
    copies_per_label = fields.Integer(
        string='Copies per Label',
        default=1,
        help='Number of copies to print for each label'
    )
    
    @api.model
    def default_get(self, fields_list):
        result = super(PrintZplLabelWizard, self).default_get(fields_list)
        
        # Set default lots/serial numbers
        if self.env.context.get('active_ids'):
            result['lot_ids'] = [(6, 0, self.env.context.get('active_ids'))]
        
        # Priority 1: Check product-level ZPL configuration for selected lots
        lot_ids = self.env.context.get('active_ids')
        if lot_ids:
            lots = self.env['stock.lot'].browse(lot_ids)
            # Check if all selected lots have the same product with ZPL configuration
            product_templates = lots.mapped('product_id.product_tmpl_id')
            if len(product_templates) == 1:  # All lots have same product
                product_template = product_templates[0]
                if product_template.zpl_label_template_id:
                    # Product has ZPL configuration, use it for template and copies
                    result['label_template_id'] = product_template.zpl_label_template_id.id
                    
                    # Set copies per label from product configuration if available
                    if (product_template.zpl_copies_per_label is not None and 
                        product_template.zpl_copies_per_label is not False):
                        result['copies_per_label'] = product_template.zpl_copies_per_label
        
        # Priority 2: Fallback to first available label template
        if 'label_template_id' not in result or not result['label_template_id']:
            labels = self.env['printing.label.zpl2'].search([
                ('model_id.model', 'in', ['stock.lot', 'mrp.production']),
                ('active', '=', True)
            ], order='name', limit=1)
            if labels:
                result['label_template_id'] = labels.id
        
        # Printer selection: ALWAYS use user configuration (regardless of product config)
        # Set default printer: prioritize user's default ZPL printer
        printer = self._get_printer_with_fallback()
        if printer:
            result['printer_id'] = printer.id
        
        return result
    
    def action_print_labels(self):
        """
        Execute label printing
        """
        if not self.lot_ids:
            raise UserError(_('Please select lots/serial numbers to print labels for.'))
        
        if not self.printer_id:
            raise UserError(_('No printer configured. Please configure a printer in user settings.'))
        
        if not self.label_template_id:
            raise UserError(_('No label template configured. Please configure a label template in user settings or product configuration.'))
        
        # Use common print method
        result = self._print_labels(
            printer=self.printer_id,
            label_template=self.label_template_id,
            records=self.lot_ids,
            copies_per_label=self.copies_per_label
        )
        
        # Display result message
        message_parts = []
        if result['success_count'] > 0:
            message_parts.append(_('Successfully printed %d labels') % result['success_count'])
        
        if result['error_messages']:
            message_parts.append(_('%d labels failed to print') % len(result['error_messages']))
        
        if message_parts:
            message_type = 'warning' if result['error_messages'] else 'success'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Printing Complete'),
                    'message': '\n'.join(message_parts),
                    'sticky': True,
                    'type': message_type,
                }
            }
        
        return {'type': 'ir.actions.act_window_close'}
    
    def action_test_print(self):
        """
        Test print functionality
        """
        if not self.label_template_id:
            raise UserError(_('Please select a label template first.'))
        
        if not self.printer_id:
            raise UserError(_('Please select a printer first.'))
        
        # Check printer status
        if self.printer_id.status != 'online':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Printer Status'),
                    'message': _('Printer %s is not online. Test print may fail.') % self.printer_id.name,
                    'sticky': False,
                    'type': 'warning',
                }
            }
        
        try:
            # Execute test print
            self.label_template_id.print_test_label(self.printer_id)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Test Print'),
                    'message': _('Test print sent to printer %s') % self.printer_id.name,
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            error_message = _('Test print failed: %s') % str(e)
            _logger.error(error_message)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Test Print Failed'),
                    'message': error_message,
                    'sticky': True,
                    'type': 'danger',
                }
            }