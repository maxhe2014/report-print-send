# Copyright (C) 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _get_zpl_printer(self, label=False):
        """Resolve the printer to use for ZPL label printing.

        Same priority as stock.picking._get_zpl_printer:
            1. User's Default Label Printer (online)
            2. Label template's own printer
            3. First active printer
            4. None
        """
        self.ensure_one()
        user = self.env.user
        if user.default_label_printer_id and user.default_label_printer_id.status == "available":
            return user.default_label_printer_id
        if label and label.printer_id:
            return label.printer_id
        printer = self.env["printing.printer"].search(
            [("active", "=", True)], limit=1
        )
        return printer or False

    def _post_put_in_pack_hook(self, package):
        picking_type = self.picking_type_id
        if (
            package
            and picking_type.auto_print_package_label
            and picking_type.package_zpl2_label_id
        ):
            label = picking_type.package_zpl2_label_id
            printer = self._get_zpl_printer(label=label)
            if not printer:
                _logger.warning(
                    "No printer available for ZPL package label %s, "
                    "skipping package %s",
                    label.name,
                    package.name,
                )
                return package
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
