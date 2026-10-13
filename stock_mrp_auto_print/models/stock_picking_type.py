# Copyright (C) 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    lot_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Lot/SN Custom ZPL Label",
        domain="[('model_id.model', '=', 'stock.lot')]",
        help=(
            "Default ZPL II label for lot/SN printing. Used when the product "
            "does not define its own ZPL label template. "
            "When a custom ZPL label is selected, the official IoT printing "
            "method is replaced by direct ZPL II printing to the configured "
            "printer."
        ),
    )
    lot_zpl2_copies = fields.Integer(
        string="Lot Label Copies",
        default=1,
        help="Default number of copies for lot/SN labels.",
    )
    package_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Package Custom ZPL Label",
        domain="[('model_id.model', '=', 'stock.package')]",
        help=(
            "Default ZPL II label for package printing. "
            "When a custom ZPL label is selected, the official IoT printing "
            "method is replaced by direct ZPL II printing to the configured "
            "printer."
        ),
    )
    package_zpl2_copies = fields.Integer(
        string="Package Label Copies",
        default=1,
        help="Default number of copies for package labels.",
    )

    # --- Manufacturing (mrp) custom ZPL labels ---
    done_mrp_lot_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Done Lot Custom ZPL Label",
        domain="[('model_id.model', '=', 'stock.lot')]",
        help=(
            "Custom ZPL II label for lot/SN printing when a manufacturing "
            "order is done. Used when the product does not define its own "
            "ZPL label template. When a custom ZPL label is selected, the "
            "official IoT printing method is replaced by direct ZPL II "
            "printing to the configured printer."
        ),
    )
    done_mrp_lot_zpl2_copies = fields.Integer(
        string="Done Lot Label Copies",
        default=1,
        help="Default number of copies for done lot/SN labels.",
    )
    generated_mrp_lot_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Generated Lot Custom ZPL Label",
        domain="[('model_id.model', '=', 'stock.lot')]",
        help=(
            "Custom ZPL II label for lot/SN printing when a new lot/SN is "
            "generated. When a custom ZPL label is selected, the official "
            "IoT printing method is replaced by direct ZPL II printing to "
            "the configured printer."
        ),
    )
    generated_mrp_lot_zpl2_copies = fields.Integer(
        string="Generated Lot Label Copies",
        default=1,
        help="Default number of copies for generated lot/SN labels.",
    )
    product_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Product Custom ZPL Label",
        domain="[('model_id.model', 'in', ['product.template', 'product.product', 'stock.move', 'mrp.production', 'stock.lot', 'stock.package'])]",
        help=(
            "Default ZPL II label for product printing. Used as a fallback "
            "when neither the product nor the scenario-specific (lot/done/"
            "generated) ZPL label is configured."
        ),
    )
    product_zpl2_copies = fields.Integer(
        string="Product Label Copies",
        default=1,
        help="Default number of copies for product labels. 0 = use default 1.",
    )

    @api.constrains(
        "lot_zpl2_copies",
        "package_zpl2_copies",
        "done_mrp_lot_zpl2_copies",
        "generated_mrp_lot_zpl2_copies",
        "product_zpl2_copies",
    )
    def _check_zpl2_copies(self):
        for record in self:
            for field_name in [
                "lot_zpl2_copies",
                "package_zpl2_copies",
                "done_mrp_lot_zpl2_copies",
                "generated_mrp_lot_zpl2_copies",
                "product_zpl2_copies",
            ]:
                value = record[field_name]
                if value is not None and value is not False:
                    if value < 0 or value > 10:
                        raise ValidationError(
                            _("%(field)s must be between 0 and 10 (0 = use default).",
                              field=record._fields[field_name].string)
                        )
