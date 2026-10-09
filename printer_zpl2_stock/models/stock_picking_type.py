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
            "does not define its own ZPL label template."
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
        help="Default ZPL II label for package printing.",
    )
    package_zpl2_copies = fields.Integer(
        string="Package Label Copies",
        default=1,
        help="Default number of copies for package labels.",
    )
