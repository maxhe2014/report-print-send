import math

from odoo import models
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
        label = (
            product_template[label_field]
            or self.picking_type_id[label_field]
        )
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
                self.env._(
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
                self.env._(
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
                self.env._(
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
                    repair._print_done_zpl2_label(label, record, copies)
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
        repairs_to_print = self.filtered(
            lambda repair: repair.picking_type_id.auto_print_done_repair_order
        )
        if repairs_to_print:
            action = self.env.ref("repair.action_report_repair_order").report_action(
                repairs_to_print.ids, config=False
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
