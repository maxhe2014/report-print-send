from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PrintZplLabelWizard(models.TransientModel):
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
        
        # Set default printer: prioritize user's default ZPL printer
        user_printer = self.env.user.zpl_printer_id
        if user_printer:
            result['printer_id'] = user_printer.id
        else:
            # If no user default printer is set, use system default logic
            printers = self.env['printing.printer'].search([])
            if len(printers) == 1:
                result['printer_id'] = printers.id
        
        # Set default label template
        labels = self.env['printing.label.zpl2'].search([
            ('model_id.model', '=', 'stock.lot'),
            ('active', '=', True)
        ], order='name', limit=1)
        if labels:
            result['label_template_id'] = labels.id
        
        return result
    
    def action_print_labels(self):
        """
        Execute label printing
        """
        if not self.lot_ids:
            raise UserError(_('Please select lots/serial numbers to print labels for.'))
        
        if not self.printer_id:
            raise UserError(_('Please select a printer.'))
        
        if not self.label_template_id:
            raise UserError(_('Please select a label template.'))
        
        success_count = 0
        error_messages = []
        
        for lot in self.lot_ids:
            try:
                # Print specified number of copies
                for copy in range(self.copies_per_label):
                    self.label_template_id.print_label(self.printer_id, lot)
                success_count += 1
            except Exception as e:
                error_message = _('Failed to print label for lot %s: %s') % (lot.name, str(e))
                error_messages.append(error_message)
                _logger.error(error_message)
        
        # Display result message
        message_parts = []
        if success_count > 0:
            message_parts.append(_('Successfully printed %d labels') % success_count)
        
        if error_messages:
            message_parts.append(_('%d labels failed to print') % len(error_messages))
        
        if message_parts:
            message_type = 'warning' if error_messages else 'success'
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
        
        # Set test mode and printer for label template
        self.label_template_id.write({
            'test_print_mode': True,
            'printer_id': self.printer_id.id
        })
        
        # Execute test print
        self.label_template_id.print_test_label()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Test Print'),
                'message': _('Test print sent to printer'),
                'sticky': False,
                'type': 'success',
            }
        }