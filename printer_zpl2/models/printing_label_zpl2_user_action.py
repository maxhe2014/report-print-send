# Copyright (C) 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


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

    _label_user_uniq = models.Constraint(
        "unique (label_id, user_id)",
        "A printer configuration already exists for this label and user.",
    )

    @api.onchange("printer_id")
    def onchange_printer_id(self):
        """Reset nothing; keep simple."""
        return
