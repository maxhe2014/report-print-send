# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    """Product template extension for ZPL label printing configuration"""
    _inherit = 'product.template'

    zpl_label_template_id = fields.Many2one(
        'printing.label.zpl2', 
        string='ZPL Label Template',
        domain="[('model_id.model', 'in', ['stock.lot', 'mrp.production'])]",
        help='Select the ZPL label template to use for this product. This template will be used for automatic label printing during manufacturing.'
    )
    zpl_copies_per_label = fields.Integer(
        string='ZPL Copies per Label', 
        default=1,
        help='Number of copies to print for each label. This setting will be used during automatic label printing.'
    )
    
    @api.constrains('zpl_copies_per_label')
    def _check_zpl_copies_per_label(self):
        """Validate ZPL copies per label value
        
        Ensures that the number of copies per label is between 1 and 500.
        """
        for record in self:
            # Allow empty value (None/False) to use user configuration
            if record.zpl_copies_per_label is not None and record.zpl_copies_per_label is not False:
                if record.zpl_copies_per_label < 1 or record.zpl_copies_per_label > 500:
                    raise ValidationError(_('ZPL copies per label must be between 1 and 500.'))