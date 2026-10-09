# Copyright (C) 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    zpl_label_template_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="ZPL Label Template",
        domain="[('model_id.model', 'in', ['stock.lot', 'stock.package'])]",
        help=(
            "Select the ZPL label template to use for this product. "
            "This template takes priority over the operation type's "
            "default ZPL label during automatic printing."
        ),
    )
    zpl_copies_per_label = fields.Integer(
        string="ZPL Copies per Label",
        default=1,
        help="Number of copies to print for each label.",
    )

    @api.constrains("zpl_copies_per_label")
    def _check_zpl_copies_per_label(self):
        for record in self:
            if (
                record.zpl_copies_per_label is not None
                and record.zpl_copies_per_label is not False
            ):
                if record.zpl_copies_per_label < 1 or record.zpl_copies_per_label > 6:
                    raise ValidationError(
                        _("ZPL copies per label must be between 1 and 6.")
                    )
