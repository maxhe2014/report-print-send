# Copyright 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    auto_print_done_repair_order = fields.Boolean(
        string="Auto Print Completed Repair Order",
        help="Automatically print the repair order when the repair is completed.",
    )
    repair_order_label_to_print = fields.Selection(
        [("pdf", "PDF"), ("zpl", "ZPL")],
        string="Repair Order Label Format",
        default="pdf",
        help=(
            "Format used when auto-printing the repair order document after "
            "a repair is completed. PDF uses the native Odoo repair report; "
            "ZPL uses the custom ZPL II label configured below."
        ),
    )
    repair_order_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Default Repair Order ZPL II Label",
        domain="[('model_id.model', '=', 'repair.order')]",
        help=(
            "Custom ZPL II label for the repair order document. Used when "
            "repair_order_label_to_print is set to ZPL. If not set, the "
            "operation type does not auto-print ZPL for repair orders; use "
            "PDF instead."
        ),
    )
    repair_order_zpl2_copies = fields.Integer(
        string="Default Repair Order ZPL Copies",
        default=1,
        help=(
            "Default number of custom ZPL II repair order labels per repair "
            "order. 0 = use default 1."
        ),
    )
    auto_print_done_repair_product_labels = fields.Boolean(
        string="Auto Print Repaired Product Labels",
        help="Automatically print repaired product labels when the repair is completed.",
    )
    repair_product_label_to_print = fields.Selection(
        [("pdf", "PDF"), ("zpl", "ZPL")],
        string="Repair Product Label Format",
        default="pdf",
    )
    auto_print_done_repair_lot = fields.Boolean(
        string="Auto Print Repaired Lot Label",
        help="Automatically print the lot/serial number label when the repair is completed.",
    )
    done_repair_lot_label_to_print = fields.Selection(
        [("pdf", "PDF"), ("zpl", "ZPL")],
        string="Repair Lot/SN Label Format",
        default="pdf",
    )
    repair_product_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Default Repair Product ZPL II Label",
        domain=[
            (
                "model_id.model",
                "in",
                ["repair.order", "product.product", "product.template"],
            )
        ],
        help=(
            "Used when the repaired product has no repair-specific product label. "
            "A custom ZPL II label takes priority over the native label format."
        ),
    )
    repair_product_zpl2_copies = fields.Integer(
        string="Default Repair Product Label Copies",
        default=1,
        help="Default number of custom ZPL II product labels per repair order.",
    )
    done_repair_lot_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Default Repair Lot/SN ZPL II Label",
        domain=[("model_id.model", "=", "stock.lot")],
        help=(
            "Used when the repaired product has no repair-specific lot/SN label. "
            "A custom ZPL II label takes priority over the native label format."
        ),
    )
    done_repair_lot_zpl2_copies = fields.Integer(
        string="Default Repair Lot/SN Label Copies",
        default=1,
        help=(
            "Default number of custom ZPL II lot/SN labels per repaired unit, "
            "rounded up."
        ),
    )

    @api.constrains(
        "repair_order_zpl2_copies",
        "repair_product_zpl2_copies",
        "done_repair_lot_zpl2_copies",
    )
    def _check_repair_zpl2_copies(self):
        for record in self:
            for field_name in (
                "repair_order_zpl2_copies",
                "repair_product_zpl2_copies",
                "done_repair_lot_zpl2_copies",
            ):
                value = record[field_name]
                if not 1 <= value <= 10:
                    raise ValidationError(
                        _(
                            "%(field)s must be between 1 and 10.",
                            field=record._fields[field_name].string,
                        )
                    )
