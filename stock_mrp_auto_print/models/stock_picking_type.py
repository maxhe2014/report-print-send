# Copyright (C) 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

from odoo import _, api, fields, models
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
        domain="[('model_id.model', '=', 'stock.quant.package')]",
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
        domain="[('model_id.model', 'in', ['product.template', 'product.product', 'stock.move', 'mrp.production', 'stock.lot', 'stock.quant.package'])]",
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
    production_order_label_to_print = fields.Selection(
        [("pdf", "PDF"), ("zpl", "ZPL")],
        string="Production Order Print Format",
        default="pdf",
        help=(
            "Format used when auto-printing the production order document "
            "after a MO is done. PDF uses the native Odoo report; ZPL uses "
            "the custom ZPL II label configured below."
        ),
    )
    production_order_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Production Order Custom ZPL Label",
        domain="[('model_id.model', '=', 'mrp.production')]",
        help=(
            "Custom ZPL II label for the production order document. "
            "Used when production_order_label_to_print is set to ZPL. "
            "If not set, the operation type does not auto-print ZPL for "
            "production orders; use PDF instead."
        ),
    )
    production_order_zpl2_copies = fields.Integer(
        string="Production Order ZPL Copies",
        default=1,
        help="Default number of copies for custom ZPL production order labels. 0 = use default 1.",
    )

    @api.constrains(
        "lot_zpl2_copies",
        "package_zpl2_copies",
        "done_mrp_lot_zpl2_copies",
        "generated_mrp_lot_zpl2_copies",
        "product_zpl2_copies",
        "production_order_zpl2_copies",
    )
    def _check_zpl2_copies(self):
        for record in self:
            for field_name in [
                "lot_zpl2_copies",
                "package_zpl2_copies",
                "done_mrp_lot_zpl2_copies",
                "generated_mrp_lot_zpl2_copies",
                "product_zpl2_copies",
                "production_order_zpl2_copies",
            ]:
                value = record[field_name]
                if value is not None and value is not False:
                    if value < 0 or value > 10:
                        raise ValidationError(
                            _(
                                "%(field)s must be between 0 and 10 (0 = use default).",
                                field=record._fields[field_name].string,
                            )
                        )
