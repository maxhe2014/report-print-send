# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    zpl_label_template_id = fields.Many2one(
        'printing.label.zpl2', 
        string='ZPL Label Template',
        domain="[('model_id.model', '=', 'stock.lot')]"
    )
    zpl_copies_per_label = fields.Integer(
        string='ZPL Copies per Label', 
        default=1,
        help='Number of copies to print for each label'
    )
    
    @api.constrains('zpl_copies_per_label')
    def _check_zpl_copies_per_label(self):
        """Validate ZPL copies per label value"""
        for record in self:
            # Allow empty value (None/False) to use user configuration
            if record.zpl_copies_per_label is not None and record.zpl_copies_per_label is not False:
                if record.zpl_copies_per_label < 1 or record.zpl_copies_per_label > 10:
                    raise ValidationError(_('ZPL copies per label must be between 1 and 10.'))