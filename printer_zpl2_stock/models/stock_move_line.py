# Copyright (C) 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _get_zpl_printer(self, label=False):
        """Resolve the printer for ZPL label printing.

        Priority:
            1. Per-user per-label printer (printing.label.zpl2.user.action)
            2. Label template default printer (printing.label.zpl2.printer_id)
            3. User's default label printer (res.users.default_label_printer_id)

        Raises UserError if no printer is configured or the resolved printer
        is not available.
        """
        self.ensure_one()
        user = self.env.user
        printer = False

        # Priority 1: user-label specific printer
        if label:
            user_action = self.env["printing.label.zpl2.user.action"].search(
                [
                    ("label_id", "=", label.id),
                    ("user_id", "=", user.id),
                    ("active", "=", True),
                ],
                limit=1,
            )
            if user_action.printer_id:
                printer = user_action.printer_id

        # Priority 2: label template default printer
        if not printer and label and label.printer_id:
            printer = label.printer_id

        # Priority 3: user default label printer
        if not printer:
            printer = user.default_label_printer_id

        if not printer:
            raise UserError(_(
                "Default label printer is not configured.\n"
                "Please set it in Preferences → Default Label Printer before continuing."
            ))
        if printer.status != "available":
            status_label = dict(printer._fields["status"].selection).get(
                printer.status, printer.status
            )
            raise UserError(_(
                "Default label printer '%(printer)s' is not available (status: %(status)s).\n"
                "Please check the printer connection or change the default printer.",
                printer=printer.name,
                status=status_label,
            ))
        return printer

    def _post_put_in_pack_hook(self, package):
        picking_type = self.picking_type_id
        if (
            package
            and picking_type.auto_print_package_label
            and picking_type.package_zpl2_label_id
        ):
            label = picking_type.package_zpl2_label_id
            printer = self._get_zpl_printer(label=label)
            copies = picking_type.package_zpl2_copies or 1
            try:
                zpl_content = b""
                for _ in range(int(copies)):
                    zpl_content += label._generate_zpl2_data(package)
                printer.print_document(
                    report=None,
                    content=zpl_content,
                    doc_format="raw",
                )
            except Exception:
                _logger.exception(
                    "Failed to print ZPL package label %s for package %s",
                    label.name,
                    package.name,
                )
            return package
        return super()._post_put_in_pack_hook(package)
