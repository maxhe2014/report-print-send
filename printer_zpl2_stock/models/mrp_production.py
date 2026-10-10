# Copyright (C) 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import math

from odoo import _, models
from odoo.exceptions import UserError

from odoo.addons.web.controllers.utils import clean_action

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

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

    def _resolve_lot_label(self, lot, picking_type, label_field, copies_field):
        """Resolve ZPL label template and copies for a lot.

        Template priority: product-level > picking-type-level > False
        Copies priority: product-level > picking-type-level > 1
        """
        product = lot.product_id.product_tmpl_id
        # Skip products marked as "no print"
        if product.zpl_no_print:
            return False, 0
        label = product.zpl_label_template_id or picking_type[label_field]
        copies = 1
        if product.zpl_copies_per_label and product.zpl_copies_per_label > 0:
            copies = product.zpl_copies_per_label
        elif picking_type[copies_field] and picking_type[copies_field] > 0:
            copies = picking_type[copies_field]
        return label, copies

    def _get_autoprint_done_report_actions(self):
        report_actions = []
        productions_to_print = self.filtered(
            lambda p: p.picking_type_id.auto_print_done_production_order
        )
        if productions_to_print:
            action = (
                self.env.ref("mrp.action_report_production_order")
                .report_action(productions_to_print.ids, config=False)
            )
            clean_action(action, self.env)
            report_actions.append(action)
        productions_to_print = self.filtered(
            lambda p: p.picking_type_id.auto_print_done_mrp_product_labels
        )
        productions_by_print_formats = productions_to_print.grouped(
            lambda p: p.picking_type_id.mrp_product_label_to_print
        )
        for print_format in productions_to_print.picking_type_id.mapped(
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
                moves_to_print = reception_labels_to_print.move_finished_ids.move_dest_ids
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
            all_lot_productions = self.filtered(
                lambda p: p.picking_type_id.auto_print_done_mrp_lot
                and p.move_finished_ids.move_line_ids.lot_id
            )
            # Separate productions that use a custom ZPL II label
            custom_productions = all_lot_productions.filtered(
                lambda p: p.picking_type_id.done_mrp_lot_zpl2_label_id
                or any(
                    ml.lot_id.product_id.product_tmpl_id.zpl_label_template_id
                    for ml in p.move_finished_ids.move_line_ids
                    if ml.lot_id
                )
            )
            standard_productions = all_lot_productions - custom_productions

            # Print custom ZPL II labels directly
            for production in custom_productions:
                picking_type = production.picking_type_id
                lots = production.move_finished_ids.move_line_ids.mapped("lot_id")
                for lot in lots:
                    label, copies = self._resolve_lot_label(
                        lot, picking_type,
                        "done_mrp_lot_zpl2_label_id",
                        "done_mrp_lot_zpl2_copies",
                    )
                    if not label:
                        continue
                    printer = production._get_zpl_printer()
                    try:
                        zpl_content = b""
                        for _ in range(int(copies)):
                            zpl_content += label._generate_zpl2_data(lot)
                        printer.print_document(
                            report=None, content=zpl_content, doc_format="raw"
                        )
                    except Exception:
                        _logger.exception(
                            "Failed to print done MO ZPL lot label %s for lot %s",
                            label.name, lot.name,
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
                    lambda l: not l.product_id.product_tmpl_id.zpl_no_print
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
        label = (
            pt.zpl_label_template_id
            or picking_type.generated_mrp_lot_zpl2_label_id
        )
        if label:
            printer = self._get_zpl_printer()
            copies = 1
            if pt.zpl_copies_per_label and pt.zpl_copies_per_label > 0:
                copies = pt.zpl_copies_per_label
            elif (
                picking_type.generated_mrp_lot_zpl2_copies
                and picking_type.generated_mrp_lot_zpl2_copies > 0
            ):
                copies = picking_type.generated_mrp_lot_zpl2_copies
            try:
                zpl_content = b""
                for _ in range(int(copies)):
                    zpl_content += label._generate_zpl2_data(lot_id)
                printer.print_document(
                    report=None, content=zpl_content, doc_format="raw"
                )
            except Exception:
                _logger.exception(
                    "Failed to print generated lot ZPL label %s for lot %s",
                    label.name, lot_id.name,
                )
            return None
        return super()._autoprint_generated_lot(lot_id)

    def _autoprint_mass_generated_lots(self):
        actions = []
        # Standard flow for productions without custom ZPL label
        standard_productions = self.filtered(
            lambda p: not p.picking_type_id.generated_mrp_lot_zpl2_label_id
            and not any(
                lot.product_id.product_tmpl_id.zpl_label_template_id
                for lot in p.lot_producing_ids
            )
        )
        if standard_productions:
            # Replicate core standard flow but filter out zpl_no_print lots
            productions_to_print = standard_productions.filtered(
                lambda p: p.picking_type_id.auto_print_generated_mrp_lot
            )
            productions_by_print_formats = productions_to_print.grouped(
                lambda p: p.picking_type_id.generated_mrp_lot_label_to_print
            )
            for print_format in productions_to_print.picking_type_id.mapped(
                "generated_mrp_lot_label_to_print"
            ):
                grouped_productions = productions_by_print_formats.get(print_format)
                lots_to_print = grouped_productions.mapped("lot_producing_ids")
                # Filter out lots whose product is marked as "no print"
                lots_to_print = lots_to_print.filtered(
                    lambda l: not l.product_id.product_tmpl_id.zpl_no_print
                )
                if not lots_to_print:
                    continue
                if print_format == "pdf":
                    action = self.env.ref(
                        "stock.action_report_lot_label"
                    ).report_action(lots_to_print.ids, config=False)
                elif print_format == "zpl":
                    action = self.env.ref(
                        "stock.label_lot_template"
                    ).report_action(lots_to_print.ids, config=False)
                else:
                    continue
                clean_action(action, self.env)
                actions.append(action)

        # Custom ZPL flow
        custom_productions = self - standard_productions
        for production in custom_productions:
            picking_type = production.picking_type_id
            lots = production.lot_producing_ids
            for lot in lots:
                label, copies = self._resolve_lot_label(
                    lot, picking_type,
                    "generated_mrp_lot_zpl2_label_id",
                    "generated_mrp_lot_zpl2_copies",
                )
                if not label:
                    continue
                printer = production._get_zpl_printer()
                try:
                    zpl_content = b""
                    for _ in range(int(copies)):
                        zpl_content += label._generate_zpl2_data(lot)
                    printer.print_document(
                        report=None, content=zpl_content, doc_format="raw"
                    )
                except Exception:
                    _logger.exception(
                        "Failed to print mass generated lot ZPL label %s for lot %s",
                        label.name, lot.name,
                    )
        return actions
