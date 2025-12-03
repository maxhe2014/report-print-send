# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    # 默认ZPL打印机字段
    zpl_printer_id = fields.Many2one(
        comodel_name="printing.printer",
        string="默认ZPL打印机",
        help="当用户在其它位置打印ZPL标签时，未设置关联打印机时，则选择该字段中选定的打印机进行打印"
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["zpl_printer_id"]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["zpl_printer_id"]