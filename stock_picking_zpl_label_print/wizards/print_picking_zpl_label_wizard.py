from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PrintPickingZplLabelWizard(models.TransientModel):
    _name = 'print.picking.zpl.label.wizard'
    _description = 'Picking ZPL Label Printing Wizard'
    
    picking_id = fields.Many2one(
        comodel_name='stock.picking',
        string='Picking',
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
        domain="[('model_id.model', 'in', ['stock.picking', 'stock.lot']), ('active', '=', True)]",
        help='Select the label template to use'
    )
    
    lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        string='Lots/Serial Numbers',
        required=False,
        help='Select the lots/serial numbers to print labels for (only required for stock.lot templates)'
    )
    
    copies_per_label = fields.Integer(
        string='Copies per Label',
        default=1,
        help='Number of copies to print for each label'
    )
    
    @api.depends()
    def _compute_default_printer(self):
        """Compute default printer from user preferences"""
        user = self.env.user
        for wizard in self:
            wizard.printer_id = user.zpl_printer_id
    
    @api.model
    def default_get(self, fields_list):
        result = super(PrintPickingZplLabelWizard, self).default_get(fields_list)
        
        # Set default lots/serial numbers (if available and valid)
        if self.env.context.get('active_ids'):
            # Filter out any deleted lot records
            active_ids = self.env.context.get('active_ids')
            valid_lot_ids = self.env['stock.lot'].browse(active_ids).filtered(lambda l: l.exists()).ids
            if valid_lot_ids:
                result['lot_ids'] = [(6, 0, valid_lot_ids)]
        elif self.env.context.get('default_lot_ids'):
            # Ensure the lot IDs are valid
            lot_ids_data = self.env.context.get('default_lot_ids')
            if lot_ids_data and lot_ids_data[0] == 6:  # [(6, 0, [ids])]
                lot_ids = lot_ids_data[2]
                valid_lot_ids = self.env['stock.lot'].browse(lot_ids).filtered(lambda l: l.exists()).ids
                if valid_lot_ids:
                    result['lot_ids'] = [(6, 0, valid_lot_ids)]
        
        # Set default picking
        if self.env.context.get('default_picking_id'):
            picking_id = self.env.context.get('default_picking_id')
            if self.env['stock.picking'].browse(picking_id).exists():
                result['picking_id'] = picking_id
        
        return result
    
    def action_print_labels(self):
        """Print ZPL labels for the picking or lots"""
        self.ensure_one()
        
        if not self.printer_id:
            raise UserError(_("No default printer configured. Please set up a default ZPL printer in your user preferences."))
        
        if not self.label_template_id:
            raise UserError(_("Please select a label template."))
        
        try:
            # Determine what to print based on label template model
            template_model = self.label_template_id.model_id.model
            
            if template_model == 'stock.picking':
                # Print picking label
                if not self.picking_id:
                    raise UserError(_("No picking found to print label for."))
                
                for i in range(self.copies_per_label):
                    self.label_template_id.print_label(
                        self.printer_id,
                        self.picking_id,
                        copies=1
                    )
                
                # Show success message
                message = _("Successfully printed %d label(s) for picking %s.") % (
                    self.copies_per_label,
                    self.picking_id.name
                )
                
            elif template_model == 'stock.lot':
                # Print lot labels
                if not self.lot_ids:
                    raise UserError(_("Please select at least one lot/serial number to print when using stock.lot template."))
                
                # Filter out any deleted or invalid lot records
                valid_lots = self.lot_ids.filtered(lambda l: l.exists())
                if not valid_lots:
                    raise UserError(_("No valid lots/serial numbers found to print."))
                
                for lot in valid_lots:
                    for i in range(self.copies_per_label):
                        self.label_template_id.print_label(
                            self.printer_id,
                            lot,
                            copies=1
                        )
                
                # Show success message
                message = _("Successfully printed %d label(s) for %d lot(s).") % (
                    len(valid_lots) * self.copies_per_label,
                    len(valid_lots)
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