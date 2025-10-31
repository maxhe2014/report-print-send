# Copyright (C) 2022 Raumschmiede GmbH - Christopher Hansen (<https://www.raumschmiede.de>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    default_label_printer_id = fields.Many2one(
        comodel_name="printing.printer", string="Default Label Printer"
    )

    # 兼容 Odoo 17 的字段权限处理
    def _get_readable_fields(self):
        fields = super()._get_readable_fields()
        fields.append("default_label_printer_id")
        return fields

    def _get_writeable_fields(self):
        fields = super()._get_writeable_fields()
        fields.append("default_label_printer_id")
        return fields
