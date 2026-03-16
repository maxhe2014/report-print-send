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
        domain="[('model_id.model', 'in', ['stock.picking', 'stock.move', 'stock.move.line']), ('active', '=', True)]",
        help='Select the label template to use'
    )
    
    move_ids = fields.Many2many(
        comodel_name='stock.move',
        string='Stock Moves',
        required=False,
        help='Select the stock moves to print labels for (only required for stock.move templates)'
    )
    
    move_line_ids = fields.Many2many(
        comodel_name='stock.move.line',
        string='Stock Move Lines',
        required=False,
        help='Select the stock move lines to print labels for (only required for stock.move.line templates)'
    )
    
    copies_per_label = fields.Integer(
        string='Copies per Label',
        default=1,
        help='Number of copies to print for each label'
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
        result = super(PrintPickingZplLabelWizard, self).default_get(fields_list)
        

        
        # Set default stock moves (if available and valid)
        if self.env.context.get('default_move_ids'):
            # Ensure the move IDs are valid
            move_ids_data = self.env.context.get('default_move_ids')
            if move_ids_data and move_ids_data[0] == 6:  # [(6, 0, [ids])]
                move_ids = move_ids_data[2]
                valid_move_ids = self.env['stock.move'].browse(move_ids).filtered(lambda m: m.exists()).ids
                if valid_move_ids:
                    result['move_ids'] = [(6, 0, valid_move_ids)]
        
        # Set default stock move lines (if available and valid)
        if self.env.context.get('default_move_line_ids'):
            # Ensure the move line IDs are valid
            move_line_ids_data = self.env.context.get('default_move_line_ids')
            if move_line_ids_data and move_line_ids_data[0] == 6:  # [(6, 0, [ids])]
                move_line_ids = move_line_ids_data[2]
                valid_move_line_ids = self.env['stock.move.line'].browse(move_line_ids).filtered(lambda m: m.exists()).ids
                if valid_move_line_ids:
                    result['move_line_ids'] = [(6, 0, valid_move_line_ids)]
        
        # Set default picking
        if self.env.context.get('default_picking_id'):
            picking_id = self.env.context.get('default_picking_id')
            picking = self.env['stock.picking'].browse(picking_id)
            if picking.exists():
                result['picking_id'] = picking_id
                # Automatically set stock moves from the picking
                move_ids = picking.move_ids.filtered(lambda m: m.state != 'cancel').ids
                if move_ids:
                    result['move_ids'] = [(6, 0, move_ids)]
                # Automatically set stock move lines from the picking
                move_line_ids = picking.move_line_ids.filtered(lambda m: m.state != 'cancel').ids
                if move_line_ids:
                    result['move_line_ids'] = [(6, 0, move_line_ids)]
        
        # Default label template is now set manually by the user
        
        return result
    
    def action_print_labels(self):
        """Print ZPL labels for the picking, lots, or moves"""
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
                

            
            elif template_model == 'stock.move':
                # Print move labels
                if not self.move_ids:
                    raise UserError(_("Please select at least one stock move to print when using stock.move template."))
                
                # Filter out any deleted or invalid move records
                valid_moves = self.move_ids.filtered(lambda m: m.exists())
                if not valid_moves:
                    raise UserError(_("No valid stock moves found to print."))
                
                total_labels = 0
                for move in valid_moves:
                    # Calculate total copies: copies_per_label * move quantity
                    # Get total done quantity from move lines
                    total_done = sum(line.qty_done for line in move.move_line_ids if line.qty_done > 0)
                    # Use total done quantity if available, otherwise use product_uom_qty
                    move_quantity = total_done if total_done > 0 else move.product_uom_qty
                    # Ensure move_quantity is at least 1
                    move_quantity = max(1, move_quantity)
                    total_copies = self.copies_per_label * int(move_quantity)
                    _logger.info(f"Printing label for move {move.id}, product: {move.product_id.name}, quantity: {move_quantity}, copies per label: {self.copies_per_label}, total copies: {total_copies}")
                    if total_copies > 0:
                        # Print labels one by one to ensure correct quantity
                        for i in range(total_copies):
                            self.label_template_id.print_label(
                                self.printer_id,
                                move,
                                copies=1
                            )
                            total_labels += 1
                
                # Show success message
                message = _("Successfully printed %d label(s) for %d stock move(s).") % (
                    total_labels,
                    len(valid_moves)
                )
            
            elif template_model == 'stock.move.line':
                # Print move line labels
                if not self.move_line_ids:
                    raise UserError(_("Please select at least one stock move line to print when using stock.move.line template."))
                
                # Filter out any deleted or invalid move line records
                valid_move_lines = self.move_line_ids.filtered(lambda m: m.exists())
                if not valid_move_lines:
                    raise UserError(_("No valid stock move lines found to print."))
                
                total_labels = 0
                for move_line in valid_move_lines:
                    # Calculate total copies: copies_per_label * move line quantity
                    # Use qty_done if available, otherwise use product_uom_qty
                    line_quantity = move_line.qty_done if move_line.qty_done > 0 else move_line.product_uom_qty
                    # Ensure line_quantity is at least 1
                    line_quantity = max(1, line_quantity)
                    total_copies = self.copies_per_label * int(line_quantity)
                    _logger.info(f"Printing label for move line {move_line.id}, product: {move_line.product_id.name}, quantity: {line_quantity}, copies per label: {self.copies_per_label}, total copies: {total_copies}")
                    if total_copies > 0:
                        # Print labels one by one to ensure correct quantity
                        for i in range(total_copies):
                            self.label_template_id.print_label(
                                self.printer_id,
                                move_line,
                                copies=1
                            )
                            total_labels += 1
                
                # Show success message
                message = _("Successfully printed %d label(s) for %d stock move line(s).") % (
                    total_labels,
                    len(valid_move_lines)
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