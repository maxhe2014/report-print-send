# Copyright 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

import math

from odoo import _, models
from odoo.exceptions import UserError

from odoo.addons.web.controllers.utils import clean_action


class RepairOrder(models.Model):
    _inherit = "repair.order"

    def action_repair_done(self):
        result = super().action_repair_done()
        report_actions = self._get_autoprint_done_report_actions()
        if not report_actions:
            return result
        return {
            "type": "ir.actions.client",
            "tag": "do_multi_print",
            "context": {},
            "params": {"reports": report_actions},
        }

    def _resolve_done_zpl2_label(self, label_type):
        """Return the effective repair label and copies for one repair."""
        self.ensure_one()
        prefix = "repair_product" if label_type == "product" else "done_repair_lot"
        label_field = f"{prefix}_zpl2_label_id"
        copies_field = f"{prefix}_zpl2_copies"
        product_template = self.product_id.product_tmpl_id
        # Skip products marked as "no print" for this label type
        no_print_field = (
            "repair_product_zpl_no_print" if label_type == "product"
            else "repair_lot_zpl_no_print"
        )
        if product_template[no_print_field]:
            return False, 0
        label = product_template[label_field] or self.picking_type_id[label_field]
        product_copies = product_template[copies_field]
        copies = (
            product_copies
            if product_copies > 0
            else self.picking_type_id[copies_field]
        )
        return label, max(int(copies), 1)

    def _get_done_zpl2_record(self, label, label_type):
        """Map a repair label template to the record it must receive."""
        self.ensure_one()
        if label_type == "product":
            records = {
                "repair.order": self,
                "product.product": self.product_id,
                "product.template": self.product_id.product_tmpl_id,
            }
        else:
            records = {"stock.lot": self.lot_id}
        model_name = label.model_id.model
        record = records.get(model_name)
        if not record or record._name != model_name:
            raise UserError(
                _(
                    "ZPL II label '%(label)s' for repair '%(repair)s' has an "
                    "unsupported model: %(model)s.",
                    label=label.name,
                    repair=self.display_name,
                    model=model_name or "False",
                )
            )
        return record

    def _get_done_zpl2_printer(self, label):
        """Resolve the user-label, label default, or user default printer."""
        self.ensure_one()
        user = self.env.user
        user_action = self.env["printing.label.zpl2.user.action"].search(
            [
                ("label_id", "=", label.id),
                ("user_id", "=", user.id),
                ("active", "=", True),
            ],
            limit=1,
        )
        printer = (
            user_action.printer_id
            or label.default_printer_id
            or user.default_label_printer_id
        )
        if not printer:
            raise UserError(
                _(
                    "No printer is configured for ZPL II label '%(label)s' on "
                    "repair '%(repair)s'. Configure a user-label printer, the "
                    "label's default printer, or your default label printer.",
                    label=label.name,
                    repair=self.display_name,
                )
            )
        if printer.status != "available":
            status_label = dict(
                printer._fields["status"]._description_selection(self.env)
            ).get(printer.status, printer.status)
            raise UserError(
                _(
                    "Printer '%(printer)s' for ZPL II label '%(label)s' on "
                    "repair '%(repair)s' is not available (status: %(status)s).",
                    printer=printer.name,
                    label=label.name,
                    repair=self.display_name,
                    status=status_label,
                )
            )
        return printer

    def _print_done_zpl2_label(self, label, record, count):
        """Generate and send one repair's merged raw ZPL II content."""
        self.ensure_one()
        if count <= 0:
            return
        printer = self._get_done_zpl2_printer(label)
        zpl_content = b"".join(
            label._generate_zpl2_data(record) for _copy in range(count)
        )
        printer.print_document(
            report=None,
            content=zpl_content,
            doc_format="raw",
        )

    def _resolve_repair_order_zpl_label(self, repair):
        """Resolve the ZPL II label template and copies for a repair order.

        Template priority:
            1. product.repair_order_zpl2_label_id
            2. picking_type.repair_order_zpl2_label_id

        Copies priority:
            1. product.repair_order_zpl2_copies (> 0)
            2. picking_type.repair_order_zpl2_copies (> 0)
            3. 1

        Returns (label, copies). label is False if no ZPL II label configured.
        """
        product = repair.product_id.product_tmpl_id
        # Skip products marked as "no print repair order label"
        if product.repair_order_zpl_no_print:
            return False, 0
        pt = repair.picking_type_id
        label = (
            product.repair_order_zpl2_label_id
            or pt.repair_order_zpl2_label_id
        )
        if not label:
            return False, 0
        copies = 1
        product_copies = product.repair_order_zpl2_copies
        pt_copies = pt.repair_order_zpl2_copies
        if product_copies and product_copies > 0:
            copies = product_copies
        elif pt_copies and pt_copies > 0:
            copies = pt_copies
        return label, copies

    def _print_repair_order_zpl_labels(self):
        """Directly print repair-order ZPL II labels for matching repairs.

        A repair is eligible when the operation type's auto-print switch is
        on, OR the product has both a repair-order ZPL template and copies
        > 0 (product-level override). Repairs that already resolve to a ZPL
        II label are sent directly to CUPS and returned so the caller can
        exclude them from the browser PDF report list (avoid double-print).
        """
        self.ensure_one()
        pt = self.picking_type_id
        product = self.product_id.product_tmpl_id
        eligible = pt.auto_print_done_repair_order or (
            product.repair_order_zpl2_label_id
            and product.repair_order_zpl2_copies > 0
        )
        if not eligible:
            return False
        label, copies = self._resolve_repair_order_zpl_label(self)
        if not label:
            return False
        if label.model_id.model != "repair.order":
            raise UserError(
                _(
                    "ZPL II label '%(label)s' for repair '%(repair)s' has an "
                    "unsupported model: %(model)s. A repair-order label must "
                    "be bound to repair.order.",
                    label=label.name,
                    repair=self.display_name,
                    model_name=label.model_id.model or "False",
                )
            )
        self._print_done_zpl2_label(label, self, int(copies))
        return True

    def _print_done_zpl2_labels(self):
        """Directly print custom labels and return repairs handled per type."""
        direct_product_repairs = self.browse()
        direct_lot_repairs = self.browse()
        for repair in self:
            if (
                repair.picking_type_id.auto_print_done_repair_product_labels
                and repair.product_id
            ):
                label, copies = repair._resolve_done_zpl2_label("product")
                if label:
                    record = repair._get_done_zpl2_record(label, "product")
                    # 打印份数 = 每份标签数 × 维修产品数量（向上取整）
                    count = math.ceil(repair.product_qty) * copies
                    repair._print_done_zpl2_label(label, record, count)
                    direct_product_repairs |= repair
            if (
                self.env.user.has_group("stock.group_production_lot")
                and repair.picking_type_id.auto_print_done_repair_lot
                and repair.lot_id
            ):
                label, copies = repair._resolve_done_zpl2_label("lot")
                if label:
                    record = repair._get_done_zpl2_record(label, "lot")
                    count = math.ceil(repair.product_qty) * copies
                    repair._print_done_zpl2_label(label, record, count)
                    direct_lot_repairs |= repair
        return direct_product_repairs, direct_lot_repairs

    def _get_autoprint_done_report_actions(self):
        """Directly print custom ZPL II and return native report actions."""
        direct_product_repairs, direct_lot_repairs = (
            self._print_done_zpl2_labels()
        )
        report_actions = []
        # Repair order document: split into direct ZPL II and native PDF.
        # A repair is eligible when the operation type's auto-print switch
        # is on, OR the product has both a repair-order ZPL template and
        # copies > 0 (product-level override). A repair uses direct ZPL II
        # when the product has a repair-order ZPL template, or the operation
        # type is set to ZPL and has a template. Otherwise it falls back to
        # the native PDF report.
        repair_orders_to_print = self.filtered(
            lambda repair: repair.picking_type_id.auto_print_done_repair_order
            or (
                repair.product_id.product_tmpl_id.repair_order_zpl2_label_id
                and repair.product_id.product_tmpl_id.repair_order_zpl2_copies
                > 0
            )
        )
        direct_repair_order_repairs = repair_orders_to_print.browse()
        for repair in repair_orders_to_print:
            if repair._print_repair_order_zpl_labels():
                direct_repair_order_repairs |= repair
        standard_pdf_repairs = repair_orders_to_print - direct_repair_order_repairs
        if standard_pdf_repairs:
            action = self.env.ref("repair.action_report_repair_order").report_action(
                standard_pdf_repairs.ids, config=False
            )
            clean_action(action, self.env)
            report_actions.append(action)

        repairs_to_print = (
            self.filtered(
                lambda repair: repair.picking_type_id.auto_print_done_repair_product_labels
                and repair.product_id
            )
            - direct_product_repairs
        )
        repairs_by_print_format = repairs_to_print.grouped(
            lambda repair: repair.picking_type_id.repair_product_label_to_print
        )
        for print_format in repairs_to_print.picking_type_id.mapped(
            "repair_product_label_to_print"
        ):
            repairs = repairs_by_print_format.get(print_format)
            wizard = self.env["product.label.layout"].create(
                {
                    "product_ids": repairs.product_id.ids,
                    "print_format": "4x12" if print_format == "pdf" else "zpl",
                    "custom_quantity": 1,
                }
            )
            action = wizard.process()
            clean_action(action, self.env)
            report_actions.append(action)

        if self.env.user.has_group("stock.group_production_lot"):
            repairs_to_print = (
                self.filtered(
                    lambda repair: repair.picking_type_id.auto_print_done_repair_lot
                    and repair.lot_id
                )
                - direct_lot_repairs
            )
            repairs_by_print_format = repairs_to_print.grouped(
                lambda repair: repair.picking_type_id.done_repair_lot_label_to_print
            )
            for print_format in repairs_to_print.picking_type_id.mapped(
                "done_repair_lot_label_to_print"
            ):
                repairs = repairs_by_print_format.get(print_format)
                report_xmlid = (
                    "stock.action_report_lot_label"
                    if print_format == "pdf"
                    else "stock.label_lot_template"
                )
                action = self.env.ref(report_xmlid).report_action(
                    repairs.lot_id.ids, config=False
                )
                clean_action(action, self.env)
                report_actions.append(action)
        return report_actions
