# Copyright (C) 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    zpl_label_template_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Product ZPL Label Template",
        domain="[('model_id.model', 'in', ['product.template', 'product.product', 'stock.move', 'mrp.production', 'stock.lot', 'stock.package'])]",
        help=(
            "General ZPL label template for this product. Used as fallback "
            "when the scenario-specific (created/done) template is not set. "
            "Takes priority over the operation type's default ZPL label "
            "during automatic printing."
        ),
    )
    zpl_copies_per_label = fields.Integer(
        string="Product ZPL Label Copies",
        default=0,
        help="Number of copies for the product ZPL label. 0 = use the operation type setting.",
    )
    zpl_created_lot_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Created Lot/SN ZPL Label Template",
        domain="[('model_id.model', '=', 'stock.lot')]",
        help=(
            "ZPL label template used when a lot/SN is created (generated). "
            "If not set, falls back to the product ZPL label template."
        ),
    )
    zpl_created_lot_copies = fields.Integer(
        string="Created Lot Label Copies",
        default=0,
        help="Number of copies for created lot/SN labels. 0 = use the product/operation type setting.",
    )
    zpl_done_lot_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Done Lot/SN ZPL Label Template",
        domain="[('model_id.model', '=', 'stock.lot')]",
        help=(
            "ZPL label template used when a manufacturing order is done. "
            "If not set, falls back to the product ZPL label template."
        ),
    )
    zpl_done_lot_copies = fields.Integer(
        string="Done Lot Label Copies",
        default=0,
        help="Number of copies for done lot/SN labels. 0 = use the product/operation type setting.",
    )
    zpl_no_print = fields.Boolean(
        string="No Print ZPL Label",
        help="When checked, lot/SN labels for this product are skipped during automatic printing (both ZPL and standard flows).",
    )

    @api.constrains(
        "zpl_copies_per_label",
        "zpl_created_lot_copies",
        "zpl_done_lot_copies",
    )
    def _check_zpl_copies(self):
        for record in self:
            for field_name in [
                "zpl_copies_per_label",
                "zpl_created_lot_copies",
                "zpl_done_lot_copies",
            ]:
                value = record[field_name]
                if value is not None and value is not False:
                    if value < 0 or value > 6:
                        raise ValidationError(
                            _("%(field)s must be between 0 and 6 (0 = use operation type setting).",
                              field=record._fields[field_name].string)
                        )
