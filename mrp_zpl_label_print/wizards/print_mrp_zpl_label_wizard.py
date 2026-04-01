from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..models.base_print_mixin import BasePrintMixin
import logging

_logger = logging.getLogger(__name__)

class PrintMrpZplLabelWizard(models.TransientModel, BasePrintMixin):
    _name = 'print.mrp.zpl.label.wizard'
    _description = 'Print ZPL Labels for Manufacturing Order'

    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', required=True, readonly=True)
    printer_id = fields.Many2one('printing.printer', string='Printer',
                                compute='_compute_default_printer',
                                readonly=True, store=False,
                                help='Default printer from user preferences')
    label_template_id = fields.Many2one('printing.label.zpl2', string='Label Template', required=True,
                                       domain="[('model_id.model', 'in', ['stock.lot', 'mrp.production']), ('active', '=', True)]")
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
            if record.copies_per_label < 1 or record.copies_per_label > 6:
                raise ValidationError(_('Copies per label must be between 1 and 6.'))
    
    @api.depends('label_template_id')
    def _compute_default_printer(self):
        """Compute default printer from user preferences"""
        user = self.env.user
        for wizard in self:
            # Use user's default ZPL printer
            wizard.printer_id = user.zpl_printer_id

    @api.depends('production_id')
    def _compute_available_lots(self):
        for wizard in self:
            if wizard.production_id:
                # 一次性获取所有相关数据，包括原材料和成品的移动行
                # 这样即使制造单未完成，只要有批次号就可以打印标签
                move_lines = wizard.production_id.move_raw_ids.mapped('move_line_ids') + wizard.production_id.move_finished_ids.mapped('move_line_ids')
                lot_ids = move_lines.mapped('lot_id').filtered(lambda l: l).ids
                wizard.available_lot_ids = [(6, 0, lot_ids)]
                # Set default lots if not set
                if not wizard.lot_ids and lot_ids:
                    wizard.lot_ids = [(6, 0, lot_ids)]
            else:
                wizard.available_lot_ids = False

    def _compute_available_printers(self):
        """Compute available printers for ZPL printing."""
        # This method is kept for backward compatibility
        for wizard in self:
            wizard.available_printer_ids = self.env['printing.printer'].search([('active', '=', True)])

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
            
            # 优化：批量获取所有必要数据
            production = self.env['mrp.production'].browse(production_id)
            
            # Priority 1: Check product-level ZPL configuration
            if production and production.product_id:
                product_template = production.product_id.product_tmpl_id
                if product_template.zpl_label_template_id:
                    # Product has ZPL configuration, use it for template and copies
                    res['label_template_id'] = product_template.zpl_label_template_id.id
                    
                    # Set copies per label from product configuration if available
                    if (product_template.zpl_copies_per_label is not None and 
                        product_template.zpl_copies_per_label is not False):
                        res['copies_per_label'] = product_template.zpl_copies_per_label
            
            # Priority 2: Fallback to first available label template
            if 'label_template_id' not in res or not res['label_template_id']:
                # 优化：缓存标签模板查询
                label_template = self.env['printing.label.zpl2'].search([
                    ('model_id.model', 'in', ['stock.lot', 'mrp.production'])
                ], limit=1)
                if label_template:
                    res['label_template_id'] = label_template.id
        
        # Printer is now set via _compute_default_printer method
             
        return res

    def action_print_labels(self):
        """Print ZPL labels for selected lots"""
        self.ensure_one()
        
        # Validate inputs
        if not self.printer_id:
            raise ValidationError(_("No default printer configured. Please set up a default ZPL printer in your user preferences."))
            
        if not self.label_template_id:
            raise ValidationError(_("Please select a label template."))
        
        # Optimized printing with batch processing
        success_count = 0
        error_messages = []
        
        try:
            copies_per_label = int(self.copies_per_label)
            label_template_model = self.label_template_id.model_id.model
            
            if label_template_model == 'stock.lot':
                # Print lots/serial numbers
                if not self.lot_ids:
                    raise ValidationError(_("Please select at least one lot/serial number to print."))
                
                # 批量生成ZPL数据
                zpl_content = b""
                for lot in self.lot_ids:
                    try:
                        for i in range(copies_per_label):
                            # 生成单个标签的ZPL数据
                            label_content = self.label_template_id._generate_zpl2_data(lot)
                            zpl_content += label_content
                        success_count += 1
                    except Exception as e:
                        error_message = _('Failed to generate label for lot %s: %s') % (lot.name, str(e))
                        error_messages.append(error_message)
                
                # 一次性发送所有标签
                if zpl_content:
                    try:
                        self.printer_id.print_document(None, zpl_content, format='raw')
                    except Exception as e:
                        error_messages.append(_('Failed to send print job: %s') % str(e))
            elif label_template_model == 'mrp.production':
                # Print manufacturing order
                try:
                    # 批量生成ZPL数据
                    zpl_content = b""
                    for i in range(copies_per_label):
                        label_content = self.label_template_id._generate_zpl2_data(self.production_id)
                        zpl_content += label_content
                    
                    # 一次性发送所有标签
                    if zpl_content:
                        self.printer_id.print_document(None, zpl_content, format='raw')
                        success_count += 1
                except Exception as e:
                    error_message = _('Failed to print label for manufacturing order %s: %s') % (self.production_id.name, str(e))
                    error_messages.append(error_message)
            else:
                error_messages.append(_('Unsupported label template model: %s') % label_template_model)
        except Exception as e:
            error_messages.append(str(e))
        
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
        
        # Check if we need lot_ids based on label template model
        label_template_model = self.label_template_id.model_id.model
        if label_template_model == 'stock.lot' and not self.lot_ids:
            raise ValidationError(_("Please select at least one lot to test print."))
        
        if not self.printer_id:
            raise ValidationError(_("Please select a printer first."))
        
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
            # Create test content based on label template model
            label_template_model = self.label_template_id.model_id.model
            
            if label_template_model == 'stock.lot':
                # Test print with lot
                test_lot = self.lot_ids[0]
                test_content = f"TEST PRINT - {test_lot.name}"
                message = _('Test print sent to printer %s for lot %s') % (self.printer_id.name, test_lot.name)
            else:
                # Test print with manufacturing order
                test_content = f"TEST PRINT - {self.production_id.name}"
                message = _('Test print sent to printer %s for manufacturing order %s') % (self.printer_id.name, self.production_id.name)
            
            # Send test print
            self.printer_id.print_document(
                None, 
                test_content, 
                format='raw', 
                copies=1
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Test Print'),
                    'message': message,
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