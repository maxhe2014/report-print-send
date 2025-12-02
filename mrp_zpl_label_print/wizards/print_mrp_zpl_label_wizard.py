from odoo import models, fields, api


class PrintMrpZplLabelWizard(models.TransientModel):
    _name = 'print.mrp.zpl.label.wizard'
    _description = 'Print ZPL Labels for Manufacturing Order'

    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', required=True)
    printer_id = fields.Many2one('printing.printer', string='Printer', required=True,
                                domain="[('id', 'in', available_printer_ids)]")
    label_template_id = fields.Many2one('printing.label.zpl2', string='Label Template', required=True,
                                       domain="[('model_id.model', '=', 'stock.lot')]")
    lot_ids = fields.Many2many('stock.lot', string='Lots/Serials',
                              domain="[('id', 'in', available_lot_ids)]")
    copies_per_label = fields.Integer(string='Copies per Label', default=1)
    
    # Available printers and lots
    available_printer_ids = fields.Many2many('printing.printer', compute='_compute_available_printers')
    available_lot_ids = fields.Many2many('stock.lot', compute='_compute_available_lots')

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
            
            # Set default label template
            label_template = self.env['printing.label.zpl2'].search([
                ('model_id.model', '=', 'stock.lot')
            ], limit=1)
            if label_template:
                res['label_template_id'] = label_template.id
        
        # Multi-level printer selection priority:
        # 1. ZPL label template default printer
        # 2. User's default printer
        # 3. First active printer
        
        # Get ZPL label template (if any)
        zpl_label = self.env['printing.label.zpl2'].search([
            ('model_id.model', '=', 'mrp.production')
        ], limit=1)
        
        if zpl_label and zpl_label.printing_printer_id:
            # Priority 1: ZPL label template default printer
            res['printer_id'] = zpl_label.printing_printer_id.id
        elif self.env.user.printing_printer_id:
            # Priority 2: User's default printer
            res['printer_id'] = self.env.user.printing_printer_id.id
        else:
            # Priority 3: First active printer
            printer = self.env['printing.printer'].search([('active', '=', True)], limit=1)
            if printer:
                res['printer_id'] = printer.id
            
        return res

    def action_print_labels(self):
        """Print ZPL labels for selected lots"""
        self.ensure_one()
        
        if not self.lot_ids:
            raise models.ValidationError("Please select at least one lot to print.")
        
        # Print each lot
        for lot in self.lot_ids:
            for i in range(self.copies_per_label):
                self.label_template_id.print_label(self.printer_id, lot)
        
        return {'type': 'ir.actions.act_window_close'}

    def action_test_print(self):
        """Test print functionality"""
        self.ensure_one()
        
        if not self.lot_ids:
            raise models.ValidationError("Please select at least one lot to test print.")
        
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