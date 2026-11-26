# Copyright (C) 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

import logging
import math
from collections import defaultdict

from odoo import _, models
from odoo.exceptions import UserError

from odoo.addons.web.controllers.utils import clean_action

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def _get_zpl_printer(self, label=False):
        """Resolve the printer for ZPL label printing.

        Priority:
            1. Per-user per-label printer (printing.label.zpl2.user.action)
            2. Label template default printer (printing.label.zpl2.default_printer_id)
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
        if not printer and label and label.default_printer_id:
            printer = label.default_printer_id

        # Priority 3: user default label printer
        if not printer:
            printer = user.default_label_printer_id

        if not printer:
            raise UserError(
                _(
                    "Default label printer is not configured.\n"
                    "Please set it in Preferences → Default Label Printer before continuing."
                )
            )
        if printer.status != "available":
            status_label = dict(
                printer._fields["status"]._description_selection(self.env)
            ).get(printer.status, printer.status)
            raise UserError(
                _(
                    "Default label printer '%(printer)s' is not available (status: %(status)s).\n"
                    "Please check the printer connection or change the default printer.",
                    printer=printer.name,
                    status=status_label,
                )
            )
        return printer

    def _zpl_lot_qty_by_lot(self, move_lines):
        """Return {lot_id: handled quantity} for the given move lines.

        Mirrors Odoo's "One per unit" convention for the lot quantity: lines
        whose UoM shares the reference of the unit UoM contribute their
        ``quantity``, other UoMs count as one.
        """
        uom_unit = self.env.ref("uom.product_uom_unit")
        qty_by_lot = defaultdict(float)
        for move_line in move_lines:
            if not move_line.lot_id:
                continue
            if move_line.product_uom_id._has_common_reference(uom_unit):
                qty_by_lot[move_line.lot_id.id] += move_line.quantity
            else:
                qty_by_lot[move_line.lot_id.id] += 1
        return qty_by_lot

    def _resolve_lot_label(
        self, lot, picking_type, label_field, copies_field, scenario="lot"
    ):
        """Resolve ZPL label template and copies for a lot.

        Template priority (created/done scenario):
            1. product.zpl_<scenario>_lot_label_id
            2. picking_type[label_field]
            3. picking_type.product_zpl2_label_id
        Template priority (lot scenario):
            1. product.zpl_label_template_id
            2. picking_type[label_field]
            3. picking_type.product_zpl2_label_id

        A value of 0 for copies means "not set, fall back to next level".
        """
        product = lot.product_id.product_tmpl_id
        # Skip products marked as "no print"
        if product.zpl_no_print:
            return False, 0

        # Resolve label template
        if scenario == "created":
            product_label = product.zpl_created_lot_label_id
            product_copies = (
                product.zpl_created_lot_copies or product.zpl_copies_per_label
            )
        elif scenario == "done":
            product_label = product.zpl_done_lot_label_id
            product_copies = product.zpl_done_lot_copies or product.zpl_copies_per_label
        else:  # "lot"
            product_label = product.zpl_label_template_id
            product_copies = product.zpl_copies_per_label

        label = (
            product_label
            or picking_type[label_field]
            or picking_type.product_zpl2_label_id
        )

        # Resolve copies (0 means "not set")
        copies = 1
        if product_copies and product_copies > 0:
            copies = product_copies
        elif picking_type[copies_field] and picking_type[copies_field] > 0:
            copies = picking_type[copies_field]
        elif picking_type.product_zpl2_copies and picking_type.product_zpl2_copies > 0:
            copies = picking_type.product_zpl2_copies
        return label, copies

    def _resolve_product_zpl_label(self, production):
        """Resolve the ZPL label template and copies for a production's product.

        Template priority:
            1. product.zpl_label_template_id
            2. picking_type.product_zpl2_label_id

        Copies priority:
            1. product.zpl_copies_per_label
            2. picking_type.product_zpl2_copies
            3. 1

        Returns (label, copies). label is False if no ZPL label configured.
        """
        product = production.product_id.product_tmpl_id
        if product.zpl_no_print:
            return False, 0

        pt = production.picking_type_id
        label = product.zpl_label_template_id or pt.product_zpl2_label_id
        if not label:
            return False, 0

        copies = 1
        if product.zpl_copies_per_label and product.zpl_copies_per_label > 0:
            copies = product.zpl_copies_per_label
        elif pt.product_zpl2_copies and pt.product_zpl2_copies > 0:
            copies = pt.product_zpl2_copies
        return label, copies

    def _get_zpl_record_for_label(self, production, label):
        """Return the record(s) to pass to ZPL label based on label's model_id.

        Returns a recordset. For labels whose model is ``stock.lot`` this
        returns the finished lot(s) of the production; callers should iterate
        over the result to print one label per lot.
        """
        model_name = label.model_id.model if label.model_id else False
        if model_name == "mrp.production":
            return production
        elif model_name == "product.product":
            return production.product_id
        elif model_name == "product.template":
            return production.product_id.product_tmpl_id
        elif model_name == "stock.lot":
            return production.finished_move_line_ids.mapped("lot_id")
        # Default to production record
        return production

    def _resolve_production_order_zpl_label(self, production):
        """Resolve ZPL label template and copies for the production order.

        Template priority:
            1. product.production_order_zpl2_label_id
            2. picking_type.production_order_zpl2_label_id
        Copies priority:
            1. product.production_order_zpl2_copies (> 0)
            2. picking_type.production_order_zpl2_copies (> 0)
            3. 1

        Returns (label, copies). label is False if no ZPL label configured.
        """
        product = production.product_id.product_tmpl_id
        pt = production.picking_type_id
        label = (
            product.production_order_zpl2_label_id
            or pt.production_order_zpl2_label_id
        )
        if not label:
            return False, 0
        copies = 1
        product_copies = product.production_order_zpl2_copies
        pt_copies = pt.production_order_zpl2_copies
        if product_copies and product_copies > 0:
            copies = product_copies
        elif pt_copies and pt_copies > 0:
            copies = pt_copies
        return label, copies

    def _get_autoprint_done_report_actions(self):
        report_actions = []
        # Product-level override: a product with both a production order ZPL
        # template and copies > 0 always prints, even when the operation
        # type's auto-print switch is off or its format is PDF.
        productions_to_print = self.filtered(
            lambda p: p.picking_type_id.auto_print_done_production_order
            or (
                p.product_tmpl_id.production_order_zpl2_label_id
                and p.product_tmpl_id.production_order_zpl2_copies > 0
            )
        )
        # A product ZPL template takes priority over the operation type's
        # native PDF and ZPL template settings.
        custom_zpl_productions = productions_to_print.filtered(
            lambda p: (
                p.product_tmpl_id.production_order_zpl2_label_id
                or (
                    p.picking_type_id.production_order_label_to_print == "zpl"
                    and p.picking_type_id.production_order_zpl2_label_id
                )
            )
        )
        standard_pdf_productions = productions_to_print - custom_zpl_productions

        # Custom ZPL direct printing for production order
        for production in custom_zpl_productions:
            label, copies = self._resolve_production_order_zpl_label(production)
            if not label:
                continue
            printer = production._get_zpl_printer(label=label)
            # One label per produced unit: copies x production quantity,
            # rounded up. A zero quantity is not printed.
            unit_count = math.ceil(production.product_qty or 0)
            total = int(copies) * unit_count
            if total <= 0:
                continue
            zpl_content = b""
            for _ in range(total):
                zpl_content += label._generate_zpl2_data(production)
            _logger.info(
                "ZPL direct print: production order label '%s' for MO %s "
                "(%d copies x %d units = %d labels)",
                label.name,
                production.name,
                copies,
                unit_count,
                total,
            )
            printer.print_document(
                report=None, content=zpl_content, doc_format="raw"
            )

        # Native PDF production order report
        if standard_pdf_productions:
            action = (
                self.env.ref("mrp.action_report_production_order")
                .report_action(standard_pdf_productions.ids, config=False)
            )
            clean_action(action, self.env)
            report_actions.append(action)
        # Product-level override: a product with both a ZPL template and
        # copies > 0 is always printed, even when the operation type's
        # auto-print switch is off (unless the product is marked "no print",
        # which is handled inside _resolve_product_zpl_label).
        productions_to_print = self.filtered(
            lambda p: p.picking_type_id.auto_print_done_mrp_product_labels
            or (
                p.product_tmpl_id.zpl_label_template_id
                and p.product_tmpl_id.zpl_copies_per_label > 0
            )
        )
        # Separate productions that use a custom ZPL II product label
        custom_productions = productions_to_print.filtered(
            lambda p: self._resolve_product_zpl_label(p)[0]
        )
        standard_productions = productions_to_print - custom_productions

        # Custom ZPL II direct printing for product labels
        if custom_productions:
            for production in custom_productions:
                label, copies = self._resolve_product_zpl_label(production)
                if not label:
                    continue
                printer = self._get_zpl_printer(label=label)
                records = self._get_zpl_record_for_label(production, label)
                zpl_content = b""
                for record in records:
                    for _ in range(int(copies)):
                        zpl_content += label._generate_zpl2_data(record)
                _logger.info(
                    "ZPL direct print: product label '%s' for MO %s (%d copies)",
                    label.name,
                    production.name,
                    copies,
                )
                printer.print_document(
                    report=None, content=zpl_content, doc_format="raw"
                )

        # Standard product label printing (PDF / native ZPL report)
        productions_by_print_formats = standard_productions.grouped(
            lambda p: p.picking_type_id.mrp_product_label_to_print
        )
        for print_format in standard_productions.picking_type_id.mapped(
            "mrp_product_label_to_print"
        ):
            labels_to_print = productions_by_print_formats.get(print_format)
            if print_format == "pdf":
                action = (
                    self.env.ref("mrp.action_report_finished_product")
                    .report_action(labels_to_print.ids, config=False)
                )
                clean_action(action, self.env)
                report_actions.append(action)
            elif print_format == "zpl":
                action = (
                    self.env.ref("mrp.label_manufacture_template")
                    .report_action(labels_to_print.ids, config=False)
                )
                clean_action(action, self.env)
                report_actions.append(action)
        if self.env.user.has_group("mrp.group_mrp_reception_report"):
            reception_reports_to_print = self.filtered(
                lambda p: p.picking_type_id.auto_print_mrp_reception_report
                and p.picking_type_id.code == "mrp_operation"
                and p.move_finished_ids.move_dest_ids
            )
            if reception_reports_to_print:
                action = (
                    self.env.ref("stock.stock_reception_report_action")
                    .report_action(reception_reports_to_print, config=False)
                )
                action["context"] = dict(
                    {"default_production_ids": reception_reports_to_print.ids},
                    **self.env.context,
                )
                clean_action(action, self.env)
                report_actions.append(action)
            reception_labels_to_print = self.filtered(
                lambda p: p.picking_type_id.auto_print_mrp_reception_report_labels
                and p.picking_type_id.code == "mrp_operation"
            )
            if reception_labels_to_print:
                moves_to_print = (
                    reception_labels_to_print.move_finished_ids.move_dest_ids
                )
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
        if self.env.user.has_group("stock.group_production_lot"):
            # Product-level override: a product with both a done-lot ZPL
            # template and copies > 0 is always printed, even when the
            # operation type's auto-print switch is off.
            all_lot_productions = self.filtered(
                lambda p: (
                    p.picking_type_id.auto_print_done_mrp_lot
                    or any(
                        t.zpl_done_lot_label_id and t.zpl_done_lot_copies > 0
                        for t in p.move_finished_ids.move_line_ids.lot_id.product_id.product_tmpl_id
                    )
                )
                and p.move_finished_ids.move_line_ids.lot_id
            )
            # Separate productions that use a custom ZPL II label
            custom_productions = all_lot_productions.filtered(
                lambda p: p.picking_type_id.done_mrp_lot_zpl2_label_id
                or any(
                    ml.lot_id.product_id.product_tmpl_id.zpl_done_lot_label_id
                    for ml in p.move_finished_ids.move_line_ids
                    if ml.lot_id
                )
            )
            standard_productions = all_lot_productions - custom_productions

            # Print custom ZPL II labels directly
            for production in custom_productions:
                picking_type = production.picking_type_id
                move_lines = production.move_finished_ids.move_line_ids
                qty_by_lot = production._zpl_lot_qty_by_lot(move_lines)
                for lot in move_lines.lot_id:
                    label, copies = self._resolve_lot_label(
                        lot,
                        picking_type,
                        "done_mrp_lot_zpl2_label_id",
                        "done_mrp_lot_zpl2_copies",
                        scenario="done",
                    )
                    if not label:
                        continue
                    # One label per produced unit: copies x lot quantity,
                    # rounded up. A zero quantity is not printed.
                    count = int(copies) * math.ceil(qty_by_lot.get(lot.id, 0))
                    if count <= 0:
                        continue
                    printer = production._get_zpl_printer(label=label)
                    try:
                        zpl_content = b""
                        for _ in range(count):
                            zpl_content += label._generate_zpl2_data(lot)
                        printer.print_document(
                            report=None,
                            content=zpl_content,
                            doc_format="raw",
                        )
                    except Exception:
                        _logger.exception(
                            "Failed to print done MO ZPL lot label %s for lot %s",
                            label.name,
                            lot.name,
                        )

            # Standard lot label flow
            productions_by_print_formats = standard_productions.grouped(
                lambda p: p.picking_type_id.done_mrp_lot_label_to_print
            )
            for print_format in standard_productions.picking_type_id.mapped(
                "done_mrp_lot_label_to_print"
            ):
                lots_to_print = productions_by_print_formats.get(print_format)
                lots_to_print = lots_to_print.move_finished_ids.move_line_ids.mapped(
                    "lot_id"
                )
                # Filter out lots whose product is marked as "no print"
                lots_to_print = lots_to_print.filtered(
                    lambda lot: not lot.product_id.product_tmpl_id.zpl_no_print
                )
                if not lots_to_print:
                    continue
                if print_format == "pdf":
                    action = self.env.ref(
                        "stock.action_report_lot_label"
                    ).report_action(lots_to_print.ids, config=False)
                    clean_action(action, self.env)
                    report_actions.append(action)
                elif print_format == "zpl":
                    action = self.env.ref(
                        "stock.label_lot_template"
                    ).report_action(lots_to_print.ids, config=False)
                    clean_action(action, self.env)
                    report_actions.append(action)
        return report_actions

    def _autoprint_generated_lot(self, lot_id):
        picking_type = self.picking_type_id
        pt = lot_id.product_id.product_tmpl_id
        # Skip products marked as "no print"
        if pt.zpl_no_print:
            return None
        # Resolve label and copies for "created" scenario
        label, copies = self._resolve_lot_label(
            lot_id,
            picking_type,
            "generated_mrp_lot_zpl2_label_id",
            "generated_mrp_lot_zpl2_copies",
            scenario="created",
        )
        if label:
            # One label per already produced unit. Nothing is printed while
            # no quantity has been produced yet.
            count = int(copies) * math.ceil(self.qty_producing)
            if count <= 0:
                return None
            printer = self._get_zpl_printer(label=label)
            try:
                zpl_content = b""
                for _ in range(count):
                    zpl_content += label._generate_zpl2_data(lot_id)
                printer.print_document(
                    report=None, content=zpl_content, doc_format="raw"
                )
            except Exception:
                _logger.exception(
                    "Failed to print generated lot ZPL label %s for lot %s",
                    label.name,
                    lot_id.name,
                )
            return None
        return super()._autoprint_generated_lot(lot_id)
