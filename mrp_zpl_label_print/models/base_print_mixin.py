# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _
import logging

_logger = logging.getLogger(__name__)


class BasePrintMixin(models.AbstractModel):
    _name = 'base.print.mixin'
    _description = 'Base Print Mixin'

    def _get_printer_with_fallback(self):
        """Get printer with fallback logic: user ZPL printer -> user default printer -> first active printer"""
        # Priority 1: User's default ZPL printer
        if self.env.user.zpl_printer_id and self.env.user.zpl_printer_id.status == 'online':
            return self.env.user.zpl_printer_id

        # Priority 2: User's default printer
        if self.env.user.printing_printer_id and self.env.user.printing_printer_id.status == 'online':
            return self.env.user.printing_printer_id

        # Priority 3: First active printer
        printer = self.env['printing.printer'].search([('active', '=', True), ('status', '=', 'online')], limit=1)
        return printer