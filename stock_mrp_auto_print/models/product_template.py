# Copyright (C) 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    zpl_label_template_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Product ZPL Label Template",
        domain="[('model_id.model', 'in', ['product.template', 'product.product', 'stock.move', 'mrp.production', 'stock.lot', 'stock.quant.package'])]",
        help=(
            "General ZPL label template for this product. Used for product "
            "labels and for lot/SN labels in stock pickings. "
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
            "If not set, the operation type's created lot/SN template applies."
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
            "If not set, the operation type's done lot/SN template applies."
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
    product_zpl_no_print = fields.Boolean(
        string="No Print Product Label",
        help="When checked, product labels for this product are skipped during automatic printing (both ZPL and standard PDF flows).",
    )
    production_order_zpl_no_print = fields.Boolean(
        string="No Print Production Order Label",
        help="When checked, production order ZPL labels for this product are skipped during automatic printing.",
    )
    production_order_zpl2_label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Production Order ZPL Label",
        domain="[('model_id.model', '=', 'mrp.production')]",
        help=(
            "Custom ZPL II label for the production order document when a "
            "manufacturing order is done. If not set, the operation type's "
            "production order ZPL template applies. "
            "Takes priority over the native PDF production order report."
        ),
    )
    production_order_zpl2_copies = fields.Integer(
        string="Production Order ZPL Copies",
        default=0,
        help="Number of copies for the production order ZPL label. 0 = use the operation type setting.",
    )

    @api.constrains(
        "zpl_copies_per_label",
        "zpl_created_lot_copies",
        "zpl_done_lot_copies",
        "production_order_zpl2_copies",
    )
    def _check_zpl_copies(self):
        for record in self:
            for field_name in [
                "zpl_copies_per_label",
                "zpl_created_lot_copies",
                "zpl_done_lot_copies",
                "production_order_zpl2_copies",
            ]:
                value = record[field_name]
                if value is not None and value is not False:
                    if value < 0 or value > 6:
                        raise ValidationError(
                            _(
                                "%(field)s must be between 0 and 6 (0 = use operation type setting).",
                                field=record._fields[field_name].string,
                            )
                        )
