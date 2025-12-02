from odoo import models, fields, api


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def button_mark_done(self):
        """Override the mark as done button to automatically print labels if user has configuration"""
        result = super().button_mark_done()
        
        # Check if user has default printing configuration
        user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
        
        if user_config and user_config.active:
            # Check if we have the required configuration
            if user_config.label_template_id and user_config.printer_id:
                # Get lots from finished product move lines
                lot_ids = self.move_finished_ids.mapped('move_line_ids.lot_id')
                if lot_ids:
                    # Automatically print labels
                    user_config.action_auto_print_labels(self.id)
        
        return result

    def action_open_mrp_zpl_label_wizard(self):
        """Open the ZPL label printing wizard for manufacturing orders"""
        self.ensure_one()
        
        # Get the wizard view
        view = self.env.ref('mrp_zpl_label_print.print_mrp_zpl_label_wizard_form')
        
        return {
            'name': 'Print ZPL Labels for Manufacturing Order',
            'type': 'ir.actions.act_window',
            'res_model': 'print.mrp.zpl.label.wizard',
            'view_mode': 'form',
            'view_id': view.id,
            'target': 'new',
            'context': {
                'default_production_id': self.id,
                'default_lot_ids': [(6, 0, self.move_finished_ids.mapped('move_line_ids.lot_id').ids)] if self.move_finished_ids.mapped('move_line_ids.lot_id') else False,
            },
        }