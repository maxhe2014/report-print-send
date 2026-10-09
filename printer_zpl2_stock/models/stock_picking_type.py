# Copyright (C) 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


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
