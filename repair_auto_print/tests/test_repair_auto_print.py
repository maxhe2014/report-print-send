from contextlib import contextmanager
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRepairAutoPrint(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.picking_type = cls.warehouse.repair_type_id
        cls.product_serial = cls.env["product.product"].create(
            {
                "name": "Repaired Serial Product",
                "is_storable": True,
                "tracking": "serial",
            }
        )
        cls.product_no_tracking = cls.env["product.product"].create(
            {
                "name": "Repaired Product",
                "is_storable": True,
                "tracking": "none",
            }
        )
        cls.product_lot = cls.env["product.product"].create(
            {
                "name": "Repaired Lot Product",
                "is_storable": True,
                "tracking": "lot",
            }
        )
        cls.product_templates = (
            cls.product_serial.product_tmpl_id
            | cls.product_no_tracking.product_tmpl_id
            | cls.product_lot.product_tmpl_id
        )
        cls.lot = cls.env["stock.lot"].create(
            {"name": "REPAIR-SN-001", "product_id": cls.product_serial.id}
        )
        cls.quantity_lot = cls.env["stock.lot"].create(
            {"name": "REPAIR-LOT-001", "product_id": cls.product_lot.id}
        )
        cls.printer = cls._create_printer("Repair User Printer")
        cls.label_on_repair = cls._create_zpl2_label(
            "Repair Order Label", "repair.order"
        )
        cls.label_on_product = cls._create_zpl2_label(
            "Repair Product Label", "product.product"
        )
        cls.label_on_template = cls._create_zpl2_label(
            "Repair Template Label", "product.template"
        )
        cls.lot_label = cls._create_zpl2_label("Repair Lot Label", "stock.lot")
        cls.product_override_label = cls._create_zpl2_label(
            "Product Override Label", "product.template"
        )
        cls.lot_override_label = cls._create_zpl2_label(
            "Lot Override Label", "stock.lot"
        )
        cls.env.user.group_ids |= cls.env.ref("stock.group_production_lot")

    def setUp(self):
        super().setUp()
        self.picking_type.write(
            {
                "auto_print_done_repair_order": False,
                "auto_print_done_repair_product_labels": False,
                "repair_product_label_to_print": "pdf",
                "auto_print_done_repair_lot": False,
                "done_repair_lot_label_to_print": "pdf",
                "repair_product_zpl2_label_id": False,
                "repair_product_zpl2_copies": 1,
                "done_repair_lot_zpl2_label_id": False,
                "done_repair_lot_zpl2_copies": 1,
            }
        )
        self.product_templates.write(
            {
                "repair_product_zpl2_label_id": False,
                "repair_product_zpl2_copies": 0,
                "done_repair_lot_zpl2_label_id": False,
                "done_repair_lot_zpl2_copies": 0,
            }
        )
        self.printer.status = "available"
        self.env.user.default_label_printer_id = self.printer

    @classmethod
    def _create_printer(cls, name):
        return cls.env["printing.printer"].create(
            {
                "name": name,
                "system_name": name,
                "status": "available",
            }
        )

    @classmethod
    def _create_zpl2_label(cls, name, model_name):
        return cls.env["printing.label.zpl2"].create(
            {
                "name": name,
                "model_id": cls.env["ir.model"]._get(model_name).id,
            }
        )

    def _create_repair(self, product=None, lot=None, quantity=1):
        product = product or self.product_serial
        return self.env["repair.order"].create(
            {
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_qty": quantity,
                "lot_id": lot.id if lot else False,
                "picking_type_id": self.picking_type.id,
            }
        )

    @contextmanager
    def _mock_zpl_print(self):
        label_class = self.env["printing.label.zpl2"].__class__
        printer_class = self.env["printing.printer"].__class__
        with (
            patch.object(
                label_class,
                "_generate_zpl2_data",
                autospec=True,
                return_value=b"^XA^XZ",
            ) as generate_mock,
            patch.object(
                printer_class, "print_document", autospec=True
            ) as print_mock,
        ):
            yield generate_mock, print_mock

    def test_no_auto_print_by_default(self):
        repair = self._create_repair(lot=self.lot)
        self.assertEqual(repair._get_autoprint_done_report_actions(), [])

    def test_done_without_auto_print_keeps_native_result(self):
        repair = self._create_repair(product=self.product_no_tracking)
        repair.action_repair_start()
        result = repair.action_repair_end()
        self.assertIs(result, True)
        self.assertEqual(repair.state, "done")

    def test_done_returns_multi_print_action(self):
        self.picking_type.auto_print_done_repair_order = True
        repair = self._create_repair(product=self.product_no_tracking)
        repair.action_repair_start()
        result = repair.action_repair_end()
        self.assertEqual(repair.state, "done")
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "do_multi_print")
        self.assertEqual(len(result["params"]["reports"]), 1)
        self.assertEqual(
            result["params"]["reports"][0]["report_name"],
            "repair.report_repairorder2",
        )

    def test_independent_print_switches(self):
        repair = self._create_repair(lot=self.lot)
        cases = [
            ("auto_print_done_repair_order", "repair.report_repairorder2"),
            (
                "auto_print_done_repair_product_labels",
                "product.report_producttemplatelabel4x12noprice",
            ),
            ("auto_print_done_repair_lot", "stock.report_lot_label"),
        ]
        for enabled_field, report_name in cases:
            with self.subTest(enabled_field=enabled_field):
                self.picking_type.write(
                    {
                        "auto_print_done_repair_order": False,
                        "auto_print_done_repair_product_labels": False,
                        "auto_print_done_repair_lot": False,
                        enabled_field: True,
                    }
                )
                actions = repair._get_autoprint_done_report_actions()
                self.assertEqual(len(actions), 1)
                self.assertEqual(actions[0]["report_name"], report_name)

    def test_pdf_report_actions(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_order": True,
                "auto_print_done_repair_product_labels": True,
                "repair_product_label_to_print": "pdf",
                "auto_print_done_repair_lot": True,
                "done_repair_lot_label_to_print": "pdf",
            }
        )
        repair = self._create_repair(lot=self.lot)
        actions = repair._get_autoprint_done_report_actions()
        self.assertEqual(
            [action["report_name"] for action in actions],
            [
                "repair.report_repairorder2",
                "product.report_producttemplatelabel4x12noprice",
                "stock.report_lot_label",
            ],
        )
        self.assertEqual(actions[1]["data"]["active_model"], "product.product")
        self.assertEqual(
            actions[1]["data"]["quantity_by_product"],
            {self.product_serial.id: 1},
        )

    def test_zpl_report_actions(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_label_to_print": "zpl",
                "auto_print_done_repair_lot": True,
                "done_repair_lot_label_to_print": "zpl",
            }
        )
        repair = self._create_repair(lot=self.lot)
        actions = repair._get_autoprint_done_report_actions()
        self.assertEqual(
            [action["report_name"] for action in actions],
            ["stock.label_product_product_view", "stock.label_lot_template_view"],
        )
        self.assertEqual(actions[0]["data"]["zpl_template"], "normal")

    def test_lot_label_is_skipped_without_lot(self):
        self.picking_type.auto_print_done_repair_lot = True
        repair = self._create_repair(product=self.product_no_tracking)
        self.assertEqual(repair._get_autoprint_done_report_actions(), [])

    def test_custom_product_label_models(self):
        self.picking_type.auto_print_done_repair_product_labels = True
        repair = self._create_repair()
        cases = [
            (self.label_on_repair, repair),
            (self.label_on_product, self.product_serial),
            (self.label_on_template, self.product_serial.product_tmpl_id),
        ]
        for label, expected_record in cases:
            with self.subTest(model=label.model_id.model):
                self.picking_type.repair_product_zpl2_label_id = label
                with self._mock_zpl_print() as (generate_mock, print_mock):
                    actions = repair._get_autoprint_done_report_actions()
                self.assertEqual(actions, [])
                generate_mock.assert_called_once_with(label, expected_record)
                print_mock.assert_called_once_with(
                    self.printer,
                    report=None,
                    content=b"^XA^XZ",
                    doc_format="raw",
                )

    def test_custom_lot_label_and_quantity(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_lot": True,
                "done_repair_lot_zpl2_label_id": self.lot_label.id,
                "done_repair_lot_zpl2_copies": 2,
            }
        )
        repair = self._create_repair(
            product=self.product_lot, lot=self.quantity_lot, quantity=2.1
        )
        with self._mock_zpl_print() as (generate_mock, print_mock):
            actions = repair._get_autoprint_done_report_actions()
        self.assertEqual(actions, [])
        self.assertEqual(generate_mock.call_count, 6)
        self.assertEqual(
            generate_mock.call_args.args, (self.lot_label, self.quantity_lot)
        )
        print_mock.assert_called_once_with(
            self.printer,
            report=None,
            content=b"^XA^XZ" * 6,
            doc_format="raw",
        )

    def test_product_templates_override_operation_type(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.label_on_repair.id,
                "auto_print_done_repair_lot": True,
                "done_repair_lot_zpl2_label_id": self.lot_label.id,
            }
        )
        self.product_serial.product_tmpl_id.write(
            {
                "repair_product_zpl2_label_id": self.product_override_label.id,
                "done_repair_lot_zpl2_label_id": self.lot_override_label.id,
            }
        )
        repair = self._create_repair(lot=self.lot)
        with self._mock_zpl_print() as (generate_mock, print_mock):
            actions = repair._get_autoprint_done_report_actions()
        self.assertEqual(actions, [])
        self.assertEqual(
            [call.args[0] for call in generate_mock.call_args_list],
            [self.product_override_label, self.lot_override_label],
        )
        self.assertEqual(print_mock.call_count, 2)

    def test_product_and_lot_overrides_resolve_independently(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.label_on_repair.id,
                "auto_print_done_repair_lot": True,
                "done_repair_lot_zpl2_label_id": self.lot_label.id,
            }
        )
        self.product_serial.product_tmpl_id.repair_product_zpl2_label_id = (
            self.product_override_label
        )
        repair = self._create_repair(lot=self.lot)
        with self._mock_zpl_print() as (generate_mock, _print_mock):
            repair._get_autoprint_done_report_actions()
        self.assertEqual(
            [call.args[0] for call in generate_mock.call_args_list],
            [self.product_override_label, self.lot_label],
        )

    def test_product_copy_inheritance_and_quantity_rule(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.label_on_repair.id,
                "repair_product_zpl2_copies": 3,
            }
        )
        repair = self._create_repair(quantity=4.2)
        with self._mock_zpl_print() as (generate_mock, _print_mock):
            self.assertEqual(repair._get_autoprint_done_report_actions(), [])
        self.assertEqual(generate_mock.call_count, 3)

    def test_product_copy_override(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.label_on_repair.id,
                "repair_product_zpl2_copies": 5,
            }
        )
        self.product_serial.product_tmpl_id.repair_product_zpl2_copies = 2
        repair = self._create_repair(quantity=4.2)
        with self._mock_zpl_print() as (generate_mock, _print_mock):
            repair._get_autoprint_done_report_actions()
        self.assertEqual(generate_mock.call_count, 2)

    def test_product_variants_share_repair_configuration(self):
        attribute = self.env["product.attribute"].create({"name": "Repair Size"})
        values = self.env["product.attribute.value"].create(
            [
                {"name": "Small", "attribute_id": attribute.id},
                {"name": "Large", "attribute_id": attribute.id},
            ]
        )
        template = self.env["product.template"].create(
            {
                "name": "Repair Variant Product",
                "is_storable": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": attribute.id,
                            "value_ids": [(6, 0, values.ids)],
                        },
                    )
                ],
                "repair_product_zpl2_label_id": self.product_override_label.id,
                "repair_product_zpl2_copies": 2,
            }
        )
        self.assertEqual(len(template.product_variant_ids), 2)
        for variant in template.product_variant_ids:
            repair = self._create_repair(product=variant)
            label, copies = repair._resolve_done_zpl2_label("product")
            self.assertEqual(label, self.product_override_label)
            self.assertEqual(copies, 2)

    def test_multiple_repairs_resolve_independently(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.label_on_repair.id,
            }
        )
        self.product_serial.product_tmpl_id.repair_product_zpl2_label_id = (
            self.product_override_label
        )
        repairs = self._create_repair() + self._create_repair(
            product=self.product_no_tracking
        )
        with self._mock_zpl_print() as (generate_mock, print_mock):
            actions = repairs._get_autoprint_done_report_actions()
        self.assertEqual(actions, [])
        self.assertEqual(
            [call.args[0] for call in generate_mock.call_args_list],
            [self.product_override_label, self.label_on_repair],
        )
        self.assertEqual(print_mock.call_count, 2)

    def test_custom_and_native_reports_are_mixed(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_order": True,
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.label_on_repair.id,
                "auto_print_done_repair_lot": True,
            }
        )
        repair = self._create_repair(lot=self.lot)
        with self._mock_zpl_print() as (generate_mock, print_mock):
            actions = repair._get_autoprint_done_report_actions()
        self.assertEqual(
            [action["report_name"] for action in actions],
            ["repair.report_repairorder2", "stock.report_lot_label"],
        )
        generate_mock.assert_called_once_with(self.label_on_repair, repair)
        print_mock.assert_called_once()

    def test_only_custom_print_returns_native_result(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.label_on_repair.id,
            }
        )
        repair = self._create_repair(product=self.product_no_tracking)
        repair.action_repair_start()
        with self._mock_zpl_print() as (generate_mock, print_mock):
            result = repair.action_repair_end()
        self.assertIs(result, True)
        self.assertEqual(repair.state, "done")
        generate_mock.assert_called_once()
        print_mock.assert_called_once()

    def test_custom_template_does_not_bypass_switch(self):
        self.picking_type.write(
            {
                "repair_product_zpl2_label_id": self.label_on_repair.id,
                "done_repair_lot_zpl2_label_id": self.lot_label.id,
            }
        )
        repair = self._create_repair(lot=self.lot)
        with self._mock_zpl_print() as (generate_mock, print_mock):
            self.assertEqual(repair._get_autoprint_done_report_actions(), [])
        generate_mock.assert_not_called()
        print_mock.assert_not_called()

    def test_printer_priority(self):
        label_printer = self._create_printer("Repair Label Printer")
        user_printer = self._create_printer("Repair Fallback Printer")
        repair = self._create_repair()
        self.label_on_repair.default_printer_id = label_printer
        self.env.user.default_label_printer_id = user_printer
        user_action = self.env["printing.label.zpl2.user.action"].create(
            {
                "label_id": self.label_on_repair.id,
                "user_id": self.env.user.id,
                "printer_id": self.printer.id,
            }
        )
        self.assertEqual(
            repair._get_done_zpl2_printer(self.label_on_repair), self.printer
        )
        user_action.active = False
        self.assertEqual(
            repair._get_done_zpl2_printer(self.label_on_repair), label_printer
        )
        self.label_on_repair.default_printer_id = False
        self.assertEqual(
            repair._get_done_zpl2_printer(self.label_on_repair), user_printer
        )

    def test_missing_printer_raises_error(self):
        self.env.user.default_label_printer_id = False
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.label_on_repair.id,
            }
        )
        repair = self._create_repair()
        with self._mock_zpl_print() as (generate_mock, print_mock):
            with self.assertRaises(UserError):
                repair._get_autoprint_done_report_actions()
        generate_mock.assert_not_called()
        print_mock.assert_not_called()

    def test_unavailable_printer_does_not_fall_back(self):
        self.printer.status = "unavailable"
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.label_on_repair.id,
            }
        )
        repair = self._create_repair()
        with self._mock_zpl_print() as (generate_mock, print_mock):
            with self.assertRaises(UserError):
                repair._get_autoprint_done_report_actions()
        generate_mock.assert_not_called()
        print_mock.assert_not_called()

    def test_unsupported_template_model_raises_error(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.lot_label.id,
            }
        )
        repair = self._create_repair()
        with self._mock_zpl_print() as (generate_mock, print_mock):
            with self.assertRaises(UserError):
                repair._get_autoprint_done_report_actions()
        generate_mock.assert_not_called()
        print_mock.assert_not_called()

    def test_print_failure_is_not_silently_ignored(self):
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.label_on_repair.id,
            }
        )
        repair = self._create_repair()
        with self._mock_zpl_print() as (_generate_mock, print_mock):
            print_mock.side_effect = RuntimeError("Printer connection failed")
            with self.assertRaises(RuntimeError):
                repair._get_autoprint_done_report_actions()

    def test_repair_completion_rolls_back_on_print_error(self):
        self.env.user.default_label_printer_id = False
        self.picking_type.write(
            {
                "auto_print_done_repair_product_labels": True,
                "repair_product_zpl2_label_id": self.label_on_repair.id,
            }
        )
        repair = self._create_repair(product=self.product_no_tracking)
        repair.action_repair_start()
        previous_state = repair.state
        with self.assertRaises(UserError):
            with self.cr.savepoint():
                repair.action_repair_end()
        repair.invalidate_recordset()
        self.assertEqual(repair.state, previous_state)

    def test_operation_type_copy_constraints(self):
        for field_name in (
            "repair_product_zpl2_copies",
            "done_repair_lot_zpl2_copies",
        ):
            for value in (0, 11):
                with self.subTest(field=field_name, value=value):
                    with self.assertRaises(ValidationError):
                        with self.cr.savepoint():
                            self.picking_type.write({field_name: value})

    def test_product_copy_constraints(self):
        for field_name in (
            "repair_product_zpl2_copies",
            "done_repair_lot_zpl2_copies",
        ):
            for value in (-1, 11):
                with self.subTest(field=field_name, value=value):
                    with self.assertRaises(ValidationError):
                        with self.cr.savepoint():
                            self.product_serial.product_tmpl_id.write(
                                {field_name: value}
                            )
