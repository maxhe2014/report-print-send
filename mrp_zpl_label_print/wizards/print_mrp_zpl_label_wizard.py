from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..models.base_print_mixin import BasePrintMixin
import logging

_logger = logging.getLogger(__name__)

class PrintMrpZplLabelWizard(models.TransientModel, BasePrintMixin):
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
            
            # Priority 1: Check product-level ZPL configuration
            production = self.env['mrp.production'].browse(production_id)
            if production and production.product_id:
                product_template = production.product_id.product_tmpl_id
                if product_template.zpl_label_template_id:
                    # Product has ZPL configuration, use it for template and copies
                    res['label_template_id'] = product_template.zpl_label_template_id.id
                    
                    # Set copies per label from product configuration if available
                    if (product_template.zpl_copies_per_label is not None and 
                        product_template.zpl_copies_per_label is not False):
                        res['copies_per_label'] = product_template.zpl_copies_per_label
            
            # Priority 2: Use user-level ZPL configuration (fallback)
            if 'label_template_id' not in res or not res['label_template_id']:
                user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
                if user_config and user_config.active and user_config.label_template_id:
                    res['label_template_id'] = user_config.label_template_id.id
                    res['copies_per_label'] = user_config.copies_per_label
                else:
                    # Fallback to first available label template
                    label_template = self.env['printing.label.zpl2'].search([
                        ('model_id.model', '=', 'stock.lot')
                    ], limit=1)
                    if label_template:
                        res['label_template_id'] = label_template.id
        
        # Printer selection: ALWAYS use user configuration (regardless of product config)
        # Multi-level printer selection priority:
        # 1. User's default ZPL printer (new field)
        # 2. User's default printer (original field)
        # 3. First active printer
        
        # Get printer (with fallback logic)
        printer = self._get_printer_with_fallback()
        if printer:
            res['printer_id'] = printer.id
             
        return res

    def action_print_labels(self):
        """Print ZPL labels for selected lots"""
        self.ensure_one()
        
        if not self.lot_ids:
            raise ValidationError(_("Please select at least one lot/serial number to print."))
        
        if not self.printer_id:
            raise ValidationError(_("No printer configured. Please configure a printer in user settings."))
            
        if not self.label_template_id:
            raise ValidationError(_("No label template configured. Please configure a label template in user settings or product configuration."))
        
        success_count = 0
        error_messages = []
        
        # Print each lot
        for lot in self.lot_ids:
            try:
                for i in range(self.copies_per_label):
                    self.label_template_id.print_label(self.printer_id, lot)
                    success_count += 1
            except Exception as e:
                error_msg = f"Lot {lot.name} failed to print: {str(e)}"
                error_messages.append(error_msg)
                _logger.error(error_msg)
        
        # Show result message
        if success_count > 0:
            message = _("Successfully printed %d labels") % success_count
            if error_messages:
                message += _(" but %d labels failed to print") % len(error_messages)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Printing Result'),
                    'message': message,
                    'sticky': False,
                    'type': 'success' if not error_messages else 'warning',
                }
            }
        else:
            raise UserError(_("All labels failed to print. Please check printer configuration and network connection.\nError details: %s") % '\n'.join(error_messages))
        
        return {'type': 'ir.actions.act_window_close'}

    def action_test_print(self):
        """Test print functionality"""
        self.ensure_one()
        
        if not self.lot_ids:
            raise models.ValidationError(_("Please select at least one lot to test print."))
        
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