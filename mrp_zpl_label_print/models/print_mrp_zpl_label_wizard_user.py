from odoo import models, fields, api


class PrintMrpZplLabelWizardUser(models.Model):
    _name = 'print.mrp.zpl.label.wizard.user'
    _description = 'User Default ZPL Label Printing Configuration'
    
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    active = fields.Boolean(string='Active', default=True)
    
    # Default printing configuration
    label_template_id = fields.Many2one('printing.label.zpl2', string='Default Label Template', 
                                       domain="[('model_id.model', '=', 'stock.lot')]")
    printer_id = fields.Many2one('printing.printer', string='Default Printer', 
                                domain="[('active', '=', True)]")
    copies_per_label = fields.Integer(string='Default Copies per Label', default=1)
    
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
            return False
            
        # Get lots from finished product move lines
        lot_ids = production.move_finished_ids.mapped('move_line_ids.lot_id')
        if not lot_ids:
            return False
            
        # Print each lot
        for lot in lot_ids:
            for i in range(self.copies_per_label):
                if self.label_template_id and self.printer_id:
                    self.label_template_id.print_label(self.printer_id, lot)
        
        return True