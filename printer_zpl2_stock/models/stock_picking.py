# Copyright (C) 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import math

from odoo import _, models
from odoo.exceptions import UserError

from odoo.addons.web.controllers.utils import clean_action

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_zpl_printer(self):
        """Return the user's default label printer or raise UserError.

        Only the user's default label printer is used. If it is not
        configured or not available, a UserError is raised to block the
        validation.
        """
        self.ensure_one()
        user = self.env.user
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

    def _resolve_lot_label(self, lot, picking_type):
        """Resolve the ZPL label template and copies for a given lot.

        Template priority:
            1. product.zpl_label_template_id
            2. picking_type.lot_zpl2_label_id
            3. picking_type.product_zpl2_label_id
            4. False (use standard QWeb flow)

        Copies priority:
            1. product.zpl_copies_per_label (if > 0)
            2. picking_type.lot_zpl2_copies (if > 0)
            3. picking_type.product_zpl2_copies (if > 0)
            4. 1
        """
        product = lot.product_id.product_tmpl_id
        # Skip products marked as "no print"
        if product.zpl_no_print:
            return False, 0
        label = (
            product.zpl_label_template_id
            or picking_type.lot_zpl2_label_id
            or picking_type.product_zpl2_label_id
        )
        copies = 1
        if product.zpl_copies_per_label and product.zpl_copies_per_label > 0:
            copies = product.zpl_copies_per_label
        elif picking_type.lot_zpl2_copies and picking_type.lot_zpl2_copies > 0:
            copies = picking_type.lot_zpl2_copies
        elif picking_type.product_zpl2_copies and picking_type.product_zpl2_copies > 0:
            copies = picking_type.product_zpl2_copies
        return label, copies

    def _resolve_product_zpl_label(self, move):
        """Resolve the ZPL label template and copies for a stock move's product.

        Template priority:
            1. product.zpl_label_template_id
            2. picking_type.product_zpl2_label_id

        Copies priority:
            1. product.zpl_copies_per_label
            2. picking_type.product_zpl2_copies
            3. 1

        Returns (label, copies). label is False if no ZPL label configured.
        """
        product = move.product_id.product_tmpl_id
        if product.zpl_no_print:
            return False, 0

        pt = move.picking_id.picking_type_id
        label = product.zpl_label_template_id or pt.product_zpl2_label_id
        if not label:
            return False, 0

        copies = 1
        if product.zpl_copies_per_label and product.zpl_copies_per_label > 0:
            copies = product.zpl_copies_per_label
        elif pt.product_zpl2_copies and pt.product_zpl2_copies > 0:
            copies = pt.product_zpl2_copies
        return label, copies

    def _get_zpl_record_for_move(self, move, label):
        """Return the record to pass to ZPL label based on label's model_id."""
        model_name = label.model_id.model if label.model_id else False
        if model_name == "stock.move":
            return move
        elif model_name == "product.product":
            return move.product_id
        elif model_name == "product.template":
            return move.product_id.product_tmpl_id
        # Default to move record
        return move

    def _get_autoprint_report_actions(self):
        report_actions = []
        pickings_to_print = self.filtered(
            lambda p: p.picking_type_id.auto_print_delivery_slip
        )
        if pickings_to_print:
            action = (
                self.env.ref("stock.action_report_delivery")
                .report_action(pickings_to_print.ids, config=False)
            )
            clean_action(action, self.env)
            report_actions.append(action)
        pickings_print_return_slip = self.filtered(
            lambda p: p.picking_type_id.auto_print_return_slip
        )
        if pickings_print_return_slip:
            action = (
                self.env.ref("stock.return_label_report")
                .report_action(pickings_print_return_slip.ids, config=False)
            )
            clean_action(action, self.env)
            report_actions.append(action)

        if self.env.user.has_group("stock.group_reception_report"):
            reception_reports_to_print = self.filtered(
                lambda p: p.picking_type_id.auto_print_reception_report
                and p.picking_type_id.code != "outgoing"
                and p.move_ids.move_dest_ids
            )
            if reception_reports_to_print:
                action = (
                    self.env.ref("stock.stock_reception_report_action")
                    .report_action(reception_reports_to_print, config=False)
                )
                clean_action(action, self.env)
                report_actions.append(action)
            reception_labels_to_print = self.filtered(
                lambda p: p.picking_type_id.auto_print_reception_report_labels
                and p.picking_type_id.code != "outgoing"
            )
            if reception_labels_to_print:
                moves_to_print = reception_labels_to_print.move_ids.move_dest_ids
                if moves_to_print:
                    quantities = ",".join(
                        str(qty)
                        for qty in moves_to_print.mapped(
                            lambda m: math.ceil(m.product_uom_qty)
                        )
                    )
                    data = {
                        "docids": moves_to_print.ids,
                        "quantity": quantities,
                    }
                    action = self.env.ref("stock.label_picking").report_action(
                        moves_to_print, data=data, config=False
                    )
                    clean_action(action, self.env)
                    report_actions.append(action)
        pickings_print_product_label = self.filtered(
            lambda p: p.picking_type_id.auto_print_product_labels
        )
        # Separate pickings that use a custom ZPL II product label
        custom_pickings = pickings_print_product_label.filtered(
            lambda p: any(
                self._resolve_product_zpl_label(move)[0]
                for move in p.move_ids
            )
        )
        standard_pickings = pickings_print_product_label - custom_pickings

        # Custom ZPL II direct printing for product labels
        if custom_pickings:
            printer = self._get_zpl_printer()
            for picking in custom_pickings:
                for move in picking.move_ids:
                    label, copies = self._resolve_product_zpl_label(move)
                    if not label:
                        continue
                    record = self._get_zpl_record_for_move(move, label)
                    zpl_content = b""
                    for _ in range(int(copies)):
                        zpl_content += label._generate_zpl2_data(record)
                    _logger.info(
                        "ZPL direct print: product label '%s' for move %s (%d copies)",
                        label.name, move.reference or move.id, copies,
                    )
                    printer.print_document(
                        report=None, content=zpl_content, doc_format="raw"
                    )

        # Standard product label printing via product.label.layout wizard
        pickings_by_print_formats = standard_pickings.grouped(
            lambda p: p.picking_type_id.product_label_format
        )
        for print_format in standard_pickings.picking_type_id.mapped(
            "product_label_format"
        ):
            pickings = pickings_by_print_formats.get(print_format)
            wizard = self.env["product.label.layout"].create(
                {
                    "product_ids": pickings.move_ids.product_id.ids,
                    "move_ids": pickings.move_ids.ids,
                    "move_quantity": "move",
                    "print_format": pickings.picking_type_id.product_label_format,
                }
            )
            action = wizard.process()
            if action:
                clean_action(action, self.env)
                report_actions.append(action)
        if self.env.user.has_group("stock.group_production_lot"):
            pickings_print_lot_label = self.filtered(
                lambda p: p.picking_type_id.auto_print_lot_labels
                and p.move_line_ids.lot_id
            )
            # Separate pickings that use a custom ZPL II label
            custom_pickings = pickings_print_lot_label.filtered(
                lambda p: p.picking_type_id.lot_zpl2_label_id
                or any(
                    ml.lot_id.product_id.product_tmpl_id.zpl_label_template_id
                    for ml in p.move_line_ids
                    if ml.lot_id
                )
            )
            standard_pickings = pickings_print_lot_label - custom_pickings

            # Print custom ZPL II labels directly to the printer
            for picking in custom_pickings:
                picking_type = picking.picking_type_id
                lots = picking.move_line_ids.lot_id
                for lot in lots:
                    label, copies = self._resolve_lot_label(lot, picking_type)
                    if not label:
                        continue
                    printer = picking._get_zpl_printer()
                    try:
                        # Batch-generate ZPL content for all copies
                        zpl_content = b""
                        for _ in range(int(copies)):
                            zpl_content += label._generate_zpl2_data(lot)
                        printer.print_document(
                            report=None,
                            content=zpl_content,
                            doc_format="raw",
                        )
                    except Exception:
                        _logger.exception(
                            "Failed to print ZPL lot label %s for lot %s",
                            label.name,
                            lot.name,
                        )

            # Standard lot label flow (built-in ZPL / PDF templates)
            pickings_by_print_formats = standard_pickings.grouped(
                lambda p: p.picking_type_id.lot_label_format
            )
            for print_format in standard_pickings.picking_type_id.mapped(
                "lot_label_format"
            ):
                pickings = pickings_by_print_formats.get(print_format)
                # Filter out move lines whose product is marked as "no print"
                move_lines = pickings.move_line_ids.filtered(
                    lambda ml: not ml.product_id.product_tmpl_id.zpl_no_print
                )
                if not move_lines:
                    continue
                wizard = self.env["lot.label.layout"].create(
                    {
                        "move_line_ids": move_lines.ids,
                        "label_quantity": "lots"
                        if "_lots" in print_format
                        else "units",
                        "print_format": "4x12" if "4x12" in print_format else "zpl",
                    }
                )
                action = wizard.process()
                if action:
                    clean_action(action, self.env)
                    report_actions.append(action)
        if self.env.user.has_group("stock.group_tracking_lot"):
            pickings_print_packages = self.filtered(
                lambda p: p.picking_type_id.auto_print_packages
                and p.move_line_ids.result_package_id
            )
            if pickings_print_packages:
                action = (
                    self.env.ref("stock.action_report_picking_packages")
                    .report_action(pickings_print_packages.ids, config=False)
                )
                clean_action(action, self.env)
                report_actions.append(action)
        return report_actions
