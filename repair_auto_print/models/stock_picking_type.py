from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    auto_print_done_repair_order = fields.Boolean(
        string="Auto Print Completed Repair Order",
        help="Automatically print the repair order when the repair is completed.",
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

    @api.constrains("repair_product_zpl2_copies", "done_repair_lot_zpl2_copies")
    def _check_repair_zpl2_copies(self):
        for record in self:
            for field_name in (
                "repair_product_zpl2_copies",
                "done_repair_lot_zpl2_copies",
            ):
                value = record[field_name]
                if not 1 <= value <= 10:
                    raise ValidationError(
                        self.env._(
                            "%(field)s must be between 1 and 10.",
                            field=record._fields[field_name].string,
                        )
                    )
