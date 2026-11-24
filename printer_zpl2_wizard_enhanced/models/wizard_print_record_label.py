# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PrintRecordLabel(models.TransientModel):
    """Enhance printer_zpl2's generic wizard with quantity strategies and a serial range."""

    _inherit = 'wizard.print.record.label'

    quantity_source = fields.Selection(
        selection=[
            ('per_quantity', 'By Product Quantity'),
            ('per_record', 'Per Record / Serial'),
            ('exact', 'Exact Total Labels'),
        ],
        string='Quantity Mode',
        default='per_quantity',
        required=True,
        help=(
            'By Product Quantity: one label per unit of the product, multiplied by copies. '
            'Per Record / Serial: a fixed number of labels for each record or serial. '
            'Exact Total Labels: print exactly the total number you specify.'
        ),
    )
    copies_per_label = fields.Integer(
        string='Copies per Record / Serial',
        default=1,
        help='Labels printed for each unit / record / serial, between 1 and 6.',
    )
    exact_copies = fields.Integer(
        string='Exact Total Labels',
        default=1,
        help='Total number of labels to print when Quantity Mode is Exact Total Labels.',
    )
    total_labels = fields.Integer(
        string='Total Labels',
        compute='_compute_total_labels',
        help='Number of labels that will be sent to the printer.',
    )
    available_lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        relation='wizard_print_record_label_available_lot_rel',
        column1='wizard_id',
        column2='lot_id',
        string='Available Lots/Serials',
    )
    lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        relation='wizard_print_record_label_lot_rel',
        column1='wizard_id',
        column2='lot_id',
        string='Lots/Serial Numbers',
        domain="[('id', 'in', available_lot_ids)]",
        help='Select the serial numbers to print. Only used when the label template is bound to stock.lot.',
    )
    use_lot_range = fields.Boolean(
        compute='_compute_use_lot_range',
    )

    @api.constrains('copies_per_label')
    def _check_copies_per_label(self):
        for wizard in self:
            if wizard.copies_per_label < 1 or wizard.copies_per_label > 6:
                raise UserError(_('Copies per label must be between 1 and 6.'))

    @api.constrains('exact_copies')
    def _check_exact_copies(self):
        for wizard in self:
            if wizard.exact_copies < 1 or wizard.exact_copies > 999:
                raise UserError(_('Exact total labels must be between 1 and 999.'))

    @api.depends('label_id')
    def _compute_use_lot_range(self):
        for wizard in self:
            wizard.use_lot_range = wizard.label_id.model_id.model == 'stock.lot'

    @api.depends('quantity_source', 'copies_per_label', 'exact_copies',
                 'lot_ids', 'label_id')
    def _compute_total_labels(self):
        for wizard in self:
            wizard.total_labels = sum(count for _record, count in wizard._print_plan())

    # Fields that are infrastructure rather than business relations: drilling
    # into them cannot yield a meaningful lot and only costs queries.
    _SKIP_RELATION_FIELDS = frozenset({
        'message_ids', 'message_follower_ids', 'activity_ids',
        'website_message_ids', 'rating_ids',
    })
    _SKIP_MODEL_PREFIXES = ('mail.', 'ir.', 'res.', 'base.', 'web.')
    _MAX_RELATION_DEPTH = 4

    # Model-specific quantity fields that must take priority over the generic
    # ones. On an MRP production order the form shows "qty_producing /
    # product_qty" (e.g. 1.00 / 2.00); the user wants the first number, i.e.
    # the quantity of THIS order, not the total plan quantity.
    _MODEL_QUANTITY_FIELDS = {
        'mrp.production': ('qty_producing', 'product_qty'),
    }
    # Common quantity field names across sale / purchase / stock / mrp / etc.
    _QUANTITY_FIELDS = (
        'product_qty', 'product_uom_qty', 'quantity', 'qty_done',
        'qty', 'qty_ordered', 'product_qty_done',
    )
    _LINE_FIELDS = (
        'move_line_ids', 'move_ids', 'order_line', 'move_lines', 'line_ids',
    )

    @api.model
    def _direct_lot_fields(self, model_name):
        """Fields on ``model_name`` that point straight to stock.lot."""
        if model_name not in self.env:
            return []
        return [
            name for name, field in self.env[model_name]._fields.items()
            if field.type in ('many2one', 'many2many')
            and field.comodel_name == 'stock.lot'
        ]

    @api.model
    def _relation_fields(self, model_name):
        """One2many/many2many fields worth following to find lots."""
        if model_name not in self.env:
            return []
        names = []
        for name, field in self.env[model_name]._fields.items():
            if name in self._SKIP_RELATION_FIELDS:
                continue
            if field.type not in ('one2many', 'many2many'):
                continue
            comodel = field.comodel_name or ''
            if comodel == 'stock.lot' or comodel.startswith(self._SKIP_MODEL_PREFIXES):
                continue
            names.append(name)
        return names

    @api.model
    def _lots_from_records(self, records, depth=0, visited=None):
        """Recursively collect lots reachable from ``records``."""
        lots = self.env['stock.lot']
        if not records or depth > self._MAX_RELATION_DEPTH:
            return lots
        if records._name == 'stock.lot':
            return records

        visited = visited if visited is not None else set()
        for field_name in self._direct_lot_fields(records._name):
            lots |= records.mapped(field_name)

        if depth >= self._MAX_RELATION_DEPTH:
            return lots
        for field_name in self._relation_fields(records._name):
            key = (records._name, field_name)
            if key in visited:
                continue
            visited.add(key)
            related = records.mapped(field_name)
            if related:
                lots |= self._lots_from_records(related, depth + 1, visited)
        return lots

    @api.model
    def _collect_lots(self, active_model, active_ids):
        """Collect lots from any model that carries serial/lot references.

        Two levels are supported:
        1. direct m2o/m2m fields to ``stock.lot`` (``lot_id``, ``lot_ids``,
           custom fields on sales/purchase lines, ...);
        2. related records reachable through o2m/m2m fields, e.g.
           ``stock.picking.move_line_ids.lot_id`` or
           ``repair.order.move_ids.move_line_ids.lot_id``.
        """
        lots = self.env['stock.lot']
        if not active_model or not active_ids or active_model not in self.env:
            return lots
        records = self.env[active_model].browse(active_ids).exists()
        return self._lots_from_records(records)

    @api.model
    def _record_quantity(self, record, _depth=0):
        """Return the product quantity represented by one record (1 if unknown).

        A stock.lot always represents exactly one unit. Other models are
        inspected for common quantity fields first, then their detail lines
        are summed (e.g. stock.picking -> stock.move -> quantity).
        """
        if not record or _depth > 3:
            return 0
        if record._name == 'stock.lot':
            return 1
        # Model-specific priority first (e.g. MRP: qty_producing, not total).
        seen = set()
        for field_name in self._MODEL_QUANTITY_FIELDS.get(record._name, ()):
            seen.add(field_name)
            if field_name in record._fields:
                value = record[field_name]
                if isinstance(value, (int, float)) and value > 0:
                    return value
        for field_name in self._QUANTITY_FIELDS:
            if field_name in seen:
                continue
            if field_name in record._fields:
                value = record[field_name]
                if isinstance(value, (int, float)) and value > 0:
                    return value
        total = 0.0
        for field_name in self._LINE_FIELDS:
            if field_name not in record._fields:
                continue
            for line in record[field_name]:
                total += self._record_quantity(line, _depth + 1)
            if total:
                break
        return total or 1

    def _print_objects(self):
        """Records to render. Determined by the label template's model."""
        self.ensure_one()
        if self.label_id.model_id.model == 'stock.lot':
            objects = self.lot_ids.filtered(lambda lot: lot.exists())
            if not objects:
                objects = self.available_lot_ids.filtered(lambda lot: lot.exists())
            return objects

        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        if active_model and active_model in self.env and active_ids:
            return self.env[active_model].browse(active_ids).exists()
        return self.env[active_model].browse() if active_model in self.env else self.env['stock.lot'].browse()

    def _print_plan(self):
        """Return a list of ``(record, label_count)`` tuples."""
        self.ensure_one()
        objects = self._print_objects()
        if not objects:
            return []
        copies = max(1, int(self.copies_per_label or 1))

        if self.quantity_source == 'exact':
            total = max(1, int(self.exact_copies or 1))
            # Spread the exact total across the selected objects when multiple
            # records are selected; with one record this prints N identical labels.
            return [(objects[index % len(objects)], 1) for index in range(total)]

        plan = []
        for record in objects:
            if self.quantity_source == 'per_quantity':
                quantity = max(1, int(round(self._record_quantity(record))))
                count = quantity * copies
            else:  # per_record
                count = copies
            plan.append((record, count))
        return plan

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)

        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        # Collect serials from any model that references them, not just
        # Direct lot fields and related stock move lines on any model.
        lots = self._collect_lots(active_model, active_ids)
        if lots:
            if 'available_lot_ids' in fields_list:
                result['available_lot_ids'] = [(6, 0, lots.ids)]
            if 'lot_ids' in fields_list:
                result['lot_ids'] = [(6, 0, lots.ids)]

        # The ZPL printer in the user profile takes precedence over the
        # generic wizard's "only one printer" auto-selection.
        if 'printer_id' in fields_list and self.env.user.zpl_printer_id:
            result['printer_id'] = self.env.user.zpl_printer_id.id

        return result

    def print_label(self):
        """Print according to the selected quantity strategy."""
        self.ensure_one()
        plan = self._print_plan()
        if not plan:
            raise UserError(_('No record or serial number is selected for printing.'))

        printed = 0
        try:
            for record, count in plan:
                for _index in range(count):
                    self.label_id.print_label(self.printer_id, record)
                    printed += 1
        except Exception as e:
            _logger.error('Enhanced ZPL label printing failed: %s', e)
            raise UserError(_('Label printing failed: %s') % e)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Printing Complete'),
                'message': _('Successfully printed %d label(s).') % printed,
                'type': 'success',
                'sticky': False,
            },
        }
