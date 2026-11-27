# Copyright 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    repair_order_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Repair Order ZPL II Label",
        domain="[('model_id.model', '=', 'repair.order')]",
        help=(
            "Repair-specific repair-order label shared by all variants. "
            "Takes priority over the native PDF repair order report and over "
            "the repair operation type's default template. Leave empty to use "
            "the repair operation type setting."
        ),
    )
    repair_order_zpl2_copies = fields.Integer(
        string="Repair Order Label Copies",
        default=0,
        help=(
            "Overrides the operation type's copies when greater than 0. "
            "Set to 0 to inherit the operation type setting."
        ),
    )
    repair_product_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Repair Product ZPL II Label",
        domain=[
            (
                "model_id.model",
                "in",
                ["repair.order", "product.product", "product.template"],
            )
        ],
        help=(
            "Repair-specific product label shared by all variants. Leave empty "
            "to use the repair operation type's default template."
        ),
    )
    repair_product_zpl2_copies = fields.Integer(
        string="Repair Product Label Copies",
        default=0,
        help=(
            "Overrides the operation type's copies when greater than 0. "
            "Set to 0 to inherit the operation type setting."
        ),
    )
    done_repair_lot_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Repair Lot/SN ZPL II Label",
        domain=[("model_id.model", "=", "stock.lot")],
        help=(
            "Repair-specific lot/SN label shared by all variants. Leave empty "
            "to use the repair operation type's default template."
        ),
    )
    done_repair_lot_zpl2_copies = fields.Integer(
        string="Repair Lot/SN Label Copies",
        default=0,
        help=(
            "Overrides the operation type's copies when greater than 0. "
            "Set to 0 to inherit the operation type setting."
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
                if not 0 <= value <= 10:
                    raise ValidationError(
                        _(
                            "%(field)s must be between 0 and 10 "
                            "(0 = inherit operation type setting).",
                            field=record._fields[field_name].string,
                        )
                    )
