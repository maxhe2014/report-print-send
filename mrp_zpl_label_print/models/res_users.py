# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    zpl_printer_id = fields.Many2one(
        comodel_name="printing.printer", 
        string="ZPL Label Printer",
        domain="[('active', '=', True)]",
        help="Default printer for ZPL label printing"
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["zpl_printer_id"]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["zpl_printer_id"]