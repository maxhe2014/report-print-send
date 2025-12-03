# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    # Default ZPL Printer field
    zpl_printer_id = fields.Many2one(
        comodel_name="printing.printer",
        string="Default ZPL Printer",
        help="When printing ZPL labels elsewhere, if no associated printer is set, the printer selected in this field will be used for printing"
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["zpl_printer_id"]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["zpl_printer_id"]