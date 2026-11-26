# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestWizardPrintRecordLabel(TransactionCase):
    """覆盖批次预选、数量策略、对象校验与打印合并。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.wizard_model = cls.env['wizard.print.record.label']
        cls.lot_model = cls.env['ir.model']._get('stock.lot')
        cls.picking_model = cls.env['ir.model']._get('stock.picking')
        cls.partner_model = cls.env['ir.model']._get('res.partner')

        cls.product = cls.env['product.product'].create({
            'name': 'Test ZPL Serial Product',
            'type': 'product',
            'tracking': 'lot',
        })
        cls.lot = cls.env['stock.lot'].create({
            'name': 'LOT-TEST-0001',
            'product_id': cls.product.id,
        })
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.supplier_location = cls.env.ref('stock.stock_location_suppliers')
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.picking = cls._create_done_picking(3.0)

        cls.printer = cls.env['printing.printer'].create({
            'name': 'Test ZPL Printer',
            'system_name': 'test-zpl-printer',
            'server_id': cls.env['printing.server'].create({}).id,
        })

    @classmethod
    def _create_done_picking(cls, qty, lot=None):
        """创建并验证一张入库单，产生库存量与批次关联。"""
        lot = lot or cls.lot
        picking = cls.env['stock.picking'].create({
            'picking_type_id': cls.env.ref('stock.picking_type_in').id,
            'location_id': cls.supplier_location.id,
            'location_dest_id': cls.stock_location.id,
        })
        move = cls.env['stock.move'].create({
            'name': cls.product.name,
            'product_id': cls.product.id,
            'product_uom_qty': qty,
            'product_uom': cls.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': cls.supplier_location.id,
            'location_dest_id': cls.stock_location.id,
        })
        move._action_confirm()
        # Odoo 17 在确认时会自动生成预留行，直接复用并补批次，避免重复行。
        lines = move.move_line_ids
        if lines:
            lines[0].write({'lot_id': lot.id, 'quantity': qty})
            if lines[1:]:
                lines[1:].unlink()
        else:
            cls.env['stock.move.line'].create({
                'move_id': move.id,
                'picking_id': picking.id,
                'product_id': cls.product.id,
                'lot_id': lot.id,
                'quantity': qty,
                'product_uom_id': cls.product.uom_id.id,
                'location_id': cls.supplier_location.id,
                'location_dest_id': cls.stock_location.id,
            })
        picking.with_context(skip_backorder=True).button_validate()
        return picking

    def _create_label(self, model, name='Test Label'):
        return self.env['printing.label.zpl2'].create({
            'name': name,
            'model_id': model.id,
        })

    def _create_wizard(self, label, **values):
        vals = {
            'label_id': label.id,
            'printer_id': self.printer.id,
        }
        vals.update(values)
        return self.wizard_model.create(vals)

    def test_default_get_preselects_lots_for_lot_templates(self):
        """stock.lot 模板：候选与预选都等于当前打开的批次。"""
        label = self._create_label(self.lot_model)
        label.create_action()
        values = self.wizard_model.with_context(
            active_model='stock.lot', active_ids=self.lot.ids,
        ).default_get(['label_id', 'available_lot_ids', 'lot_ids'])
        self.assertEqual(values['label_id'], label.id)
        self.assertEqual(values['available_lot_ids'], [(6, 0, self.lot.ids)])
        self.assertEqual(values['lot_ids'], [(6, 0, self.lot.ids)])

    def test_default_get_skips_lots_for_other_templates(self):
        """非 stock.lot 模板不再收集批次，避免打开向导时扫描库存流水。"""
        label = self._create_label(self.picking_model)
        label.create_action()
        values = self.wizard_model.with_context(
            active_model='stock.picking', active_ids=self.picking.ids,
        ).default_get(['available_lot_ids', 'lot_ids'])
        self.assertNotIn('available_lot_ids', values)
        self.assertNotIn('lot_ids', values)

    def test_default_get_skips_lots_for_products(self):
        """从产品模板打开产品标签时不再收集批次（原慢加载问题）。"""
        template_model = self.env['ir.model']._get('product.template')
        label = self._create_label(template_model)
        label.create_action()
        values = self.wizard_model.with_context(
            active_model='product.template',
            active_ids=self.product.product_tmpl_id.ids,
        ).default_get(['available_lot_ids', 'lot_ids'])
        self.assertNotIn('available_lot_ids', values)
        self.assertNotIn('lot_ids', values)

    def test_related_lots_follows_direct_lines_only(self):
        """预选只取记录自身及其明细行上的批次。"""
        lots = self.wizard_model._related_lots(self.picking)
        self.assertEqual(lots, self.lot)

    def test_lots_from_records_uses_quants(self):
        """候选通过库存量收集，未入库的批次不会被带入。"""
        empty_lot = self.env['stock.lot'].create({
            'name': 'LOT-TEST-NO-STOCK',
            'product_id': self.product.id,
        })
        lots = self.wizard_model._lots_from_records(self.product)
        self.assertIn(self.lot, lots)
        self.assertNotIn(empty_lot, lots)

    def test_record_quantity(self):
        """完成数量优先，批次恒为 1，其他记录回退 1。"""
        self.assertAlmostEqual(self.wizard_model._record_quantity(self.picking), 3.0)
        self.assertEqual(self.wizard_model._record_quantity(self.lot), 1)
        self.assertEqual(self.wizard_model._record_quantity(self.product), 1)

    def test_print_objects_rejects_mismatched_model(self):
        """模板模型与记录模型不一致时返回空，避免虚报张数。"""
        label = self._create_label(self.partner_model)
        wizard = self._create_wizard(label, active_model_id=self.picking_model.id)
        objects = wizard.with_context(
            active_model='stock.picking', active_ids=self.picking.ids,
        )._print_objects()
        self.assertFalse(objects)

    def test_total_labels_for_exact_mode(self):
        """精确模式按指定总张数预览。"""
        label = self._create_label(self.picking_model)
        wizard = self._create_wizard(
            label,
            quantity_source='exact',
            exact_copies=5,
            active_model_id=self.picking_model.id,
        )
        total = wizard.with_context(
            active_model='stock.picking', active_ids=self.picking.ids,
        ).total_labels
        self.assertEqual(total, 5)

    def test_print_label_merges_same_record(self):
        """同一记录的多个标签合并为一次 page_count 打印。"""
        label = self._create_label(self.lot_model)
        wizard = self._create_wizard(
            label,
            quantity_source='per_record',
            copies_per_label=4,
            lot_ids=[(6, 0, self.lot.ids)],
            active_model_id=self.lot_model.id,
        )
        with patch.object(
            type(self.env['printing.label.zpl2']), 'print_label',
        ) as mocked:
            wizard.print_label()
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.kwargs.get('page_count'), 4)

    def test_print_label_requires_selection(self):
        """序列号模板未勾选批次时给出明确错误，而不是打印全部候选。"""
        label = self._create_label(self.lot_model)
        wizard = self._create_wizard(
            label,
            lot_ids=[(6, 0, [])],
            active_model_id=self.lot_model.id,
        )
        with self.assertRaises(UserError):
            wizard.print_label()

    def test_action_shared_by_templates(self):
        """同模型模板共用动作，最后一个模板移除后动作被删除。"""
        label_a = self._create_label(self.lot_model, 'Label A')
        label_b = self._create_label(self.lot_model, 'Label B')
        label_a.create_action()
        label_b.create_action()
        action = label_a.action_window_id
        self.assertTrue(action)
        self.assertEqual(action, label_b.action_window_id)

        label_a.unlink_action()
        self.assertTrue(action.exists())
        self.assertFalse(label_a.action_window_id)

        label_b.unlink_action()
        self.assertFalse(action.exists())
