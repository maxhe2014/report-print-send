# Copyright (C) 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

from odoo import fields, models


class PrintingLabelZpl2UserAction(models.Model):
    _name = "printing.label.zpl2.user.action"
    _description = "ZPL Label User Printer Action"

    label_id = fields.Many2one(
        comodel_name="printing.label.zpl2",
        string="Label",
        required=True,
        ondelete="cascade",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        ondelete="cascade",
    )
    printer_id = fields.Many2one(
        comodel_name="printing.printer",
        string="Printer",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "label_user_uniq",
            "unique(label_id, user_id)",
            "A printer configuration already exists for this label and user.",
        )
    ]
