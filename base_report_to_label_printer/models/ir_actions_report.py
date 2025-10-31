# Copyright (C) 2022 Raumschmiede GmbH - Christopher Hansen (<https://www.raumschmiede.de>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    label = fields.Boolean(string="Report is a Label")

    def _get_user_default_printer(self, user):
        """兼容 Odoo 17 和 Odoo 18
        在 Odoo 17 中，这个方法可能不存在于父类中
        """
        if self.label:
            return user.default_label_printer_id
        # 检查父类是否有这个方法
        if hasattr(super(IrActionsReport, self), '_get_user_default_printer'):
            return super()._get_user_default_printer(user)
        # Odoo 17 的默认实现
        return user.printing_printer_id or self.env['printing.printer'].get_default()
