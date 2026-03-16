# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PrintingLabelZpl2Configuration(models.Model):
    _name = "printing.label.zpl2.configuration"
    _description = "ZPL Label Printer Configuration"
    
    name = fields.Char(
        string="Name",
        required=True,
        help="Configuration name"
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        ondelete="cascade",
        help="User for whom this configuration applies"
    )
    label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Label Template",
        required=True,
        ondelete="cascade",
        help="Label template for this configuration"
    )
    printer_id = fields.Many2one(
        comodel_name="printing.printer",
        string="Printer",
        help="Printer to use for this label template"
    )
    
    _sql_constraints = [
        ('unique_user_label', 'unique(user_id, label_id)', 'A configuration already exists for this user and label template!'),
    ]
    
    def action_copy(self):
        """Copy the configuration and open it for editing"""
        self.ensure_one()
        new_name = f"{self.name} (Copy)"
        # Check if the name already exists and increment if necessary
        counter = 1
        while self.search([('name', '=', new_name)]):
            new_name = f"{self.name} (Copy {counter})"
            counter += 1
        
        # Create the copy but don't save it yet
        new_config = self.copy({
            'name': new_name,
            'user_id': False,  # Clear user to avoid unique constraint
            'label_id': False,  # Clear label to avoid unique constraint
        })
        
        # Open the new configuration for editing
        return {
            'type': 'ir.actions.act_window',
            'name': 'Copy ZPL Label Configuration',
            'res_model': 'printing.label.zpl2.configuration',
            'res_id': new_config.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_delete(self):
        """Delete the configuration"""
        self.ensure_one()
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': 'ZPL Label Printer Configurations',
            'res_model': 'printing.label.zpl2.configuration',
            'view_mode': 'tree,form',
            'target': 'current',
        }
