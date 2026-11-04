from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

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

    @api.constrains("repair_product_zpl2_copies", "done_repair_lot_zpl2_copies")
    def _check_repair_zpl2_copies(self):
        for record in self:
            for field_name in (
                "repair_product_zpl2_copies",
                "done_repair_lot_zpl2_copies",
            ):
                value = record[field_name]
                if not 0 <= value <= 10:
                    raise ValidationError(
                        self.env._(
                            "%(field)s must be between 0 and 10 "
                            "(0 = inherit operation type setting).",
                            field=record._fields[field_name].string,
                        )
                    )
