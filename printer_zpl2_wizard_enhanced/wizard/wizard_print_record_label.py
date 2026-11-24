# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import groupby

_logger = logging.getLogger(__name__)


class PrintRecordLabel(models.TransientModel):
    """Enhance printer_zpl2's generic wizard with quantity strategies and a serial range."""

    _inherit = 'wizard.print.record.label'

    # Base printer_zpl2 filters label templates solely by context['active_model'].
    # Two things break in real deployments:
    #   1. actions opened from a menu may only carry default_active_model_id
    #      (an ir.model id), so the base domain resolves to model = False;
    #   2. every template of the model shows up, even ones the user never
    #      enabled via "Add in the 'Action' menu".
    # We resolve the model from every available source and restrict the list to
    # templates that are actually bound to an action menu entry.
    label_id = fields.Many2one(
        comodel_name='printing.label.zpl2',
        domain=lambda self: self._label_domain(),
    )

    @api.model
    def _context_model(self):
        """Resolve the target model from context (safe during default_get)."""
        ctx = self.env.context
        model = ctx.get('active_model')
        if model and model in self.env:
            return model
        model_id = ctx.get('default_active_model_id')
        if model_id:
            ir_model = self.env['ir.model'].browse(model_id).exists()
            if ir_model.model in self.env:
                return ir_model.model
        # The web client injects action_id when it opens an act_window. The
        # action's binding_model_id is the most reliable model hint here: it is
        # stored on the action itself and does not depend on the action's own
        # context surviving the trip into the wizard.
        action_id = ctx.get('action_id')
        if not action_id and isinstance(ctx.get('action'), dict):
            action_id = ctx['action'].get('id')
        if action_id:
            action = self.env['ir.actions.act_window'].browse(action_id).exists()
            if action.binding_model_id and action.binding_model_id.model in self.env:
                return action.binding_model_id.model
        _logger.debug(
            'ZPL label domain: no model resolved. ctx keys=%s '
            'active_model=%s default_active_model_id=%s action_id=%s',
            sorted(k for k in ctx.keys() if not k.startswith('_')),
            ctx.get('active_model'), ctx.get('default_active_model_id'), action_id,
        )
        return False

    def _effective_model(self):
        """Context first, then the wizard's own active_model_id field."""
        model = self._context_model()
        if model:
            return model
        for record in self:
            if record.active_model_id and record.active_model_id.model in self.env:
                return record.active_model_id.model
        return False

    @api.model
    def _label_domain(self):
        model = self._context_model()
        domain = [('action_window_id', '!=', False)]
        if model:
            domain.append(('model_id.model', '=', model))
        return domain

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
                raise ValidationError(_('Copies per label must be between 1 and 6.'))

    @api.constrains('exact_copies')
    def _check_exact_copies(self):
        for wizard in self:
            if wizard.exact_copies < 1 or wizard.exact_copies > 999:
                raise ValidationError(_('Exact total labels must be between 1 and 999.'))

    @api.depends('label_id.model_id.model')
    def _compute_use_lot_range(self):
        for wizard in self:
            wizard.use_lot_range = wizard.label_id.model_id.model == 'stock.lot'

    @api.depends('quantity_source', 'copies_per_label', 'exact_copies',
                 'lot_ids', 'label_id')
    @api.depends_context('active_model', 'active_ids')
    def _compute_total_labels(self):
        for wizard in self:
            wizard.total_labels = sum(count for _record, count in wizard._print_plan())

    # Fields that are infrastructure or the whole transactional history rather
    # than business relations: drilling into them cannot yield a new lot and
    # only costs queries. ``stock_quant_ids`` still exposes the current lots of
    # a product, so skipping ``stock_move_ids`` is safe.
    _SKIP_RELATION_FIELDS = frozenset({
        'message_ids', 'message_follower_ids', 'activity_ids',
        'website_message_ids', 'rating_ids', 'stock_move_ids',
    })
    # Stock quants are only candidates, never a default selection: preselecting
    # them would print every lot of the product when the user does not choose.
    _PREFILL_SKIP_FIELDS = frozenset({'stock_quant_ids'})
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
    # Actual/done quantities come first: a validated move must print what was
    # really produced, not its initial demand. ``product_uom_qty`` is only used
    # when nothing was done yet (draft orders/pickings).
    _QUANTITY_FIELDS = (
        'quantity', 'qty_done', 'product_qty_done',
        'product_qty', 'product_uom_qty', 'qty_ordered', 'qty',
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
    def _lots_from_records(self, records):
        """Collect every lot reachable from ``records``, level by level.

        Records of the same model reached through different paths are merged at
        each level. This keeps the traversal bounded (one query per model and
        relation per level) while never skipping a relation, which a per-path
        ``visited`` set used to do (e.g. mrp.production.move_ids vs move_raw_ids).
        """
        lots = self.env['stock.lot']
        if not records:
            return lots
        level = {records._name: records}
        for depth in range(self._MAX_RELATION_DEPTH + 1):
            next_level = {}
            for model_name, model_records in level.items():
                if model_name == 'stock.lot':
                    lots |= model_records
                    continue
                for field_name in self._direct_lot_fields(model_name):
                    lots |= model_records.mapped(field_name)
                if depth >= self._MAX_RELATION_DEPTH:
                    continue
                for field_name in self._relation_fields(model_name):
                    related = model_records.mapped(field_name)
                    if related:
                        next_level[related._name] = (
                            next_level[related._name] | related
                            if related._name in next_level else related
                        )
            level = next_level
            if not level:
                break
        return lots

    @api.model
    def _collect_lots(self, active_model, active_ids):
        """Return ``(available_lots, preselected_lots)`` for the action records.

        Lots are collected from any model that carries serial/lot references:
        direct m2o/m2m fields to ``stock.lot`` (``lot_id``, ``lot_ids``, custom
        fields on sale/purchase lines, ...) and related records reachable
        through o2m/m2m fields, e.g. ``stock.picking.move_line_ids.lot_id``.

        ``preselected_lots`` only contains the lots attached to the records
        themselves, so opening the wizard on a product does not default to
        printing every lot of that product.
        """
        empty = self.env['stock.lot']
        if not active_model or not active_ids or active_model not in self.env:
            return empty, empty
        records = self.env[active_model].browse(active_ids).exists()
        return self._lots_from_records(records), self._related_lots(records)

    @api.model
    def _related_lots(self, records):
        """Lots directly attached to ``records`` or to their immediate lines."""
        lots = self.env['stock.lot']
        if not records:
            return lots
        if records._name == 'stock.lot':
            return records
        for field_name in self._direct_lot_fields(records._name):
            lots |= records.mapped(field_name)
        for field_name in self._relation_fields(records._name):
            if field_name in self._PREFILL_SKIP_FIELDS:
                continue
            # Only follow relations whose target carries a direct lot field
            # (e.g. move_line_ids -> lot_id). This skips attribute lines,
            # packaging, backorders... and avoids selecting lots of other
            # documents than the ones currently opened.
            comodel = records._fields[field_name].comodel_name
            if not comodel or not self._direct_lot_fields(comodel):
                continue
            related = records.mapped(field_name)
            if not related:
                continue
            for lot_field in self._direct_lot_fields(related._name):
                lots |= related.mapped(lot_field)
        return lots

    @api.model
    def _quantity_from_fields(self, record):
        """Model-specific quantity field first, then the generic candidates."""
        priority = self._MODEL_QUANTITY_FIELDS.get(record._name, ())
        candidates = [
            name for name in self._QUANTITY_FIELDS if name not in priority
        ]
        for field_name in (*priority, *candidates):
            if field_name in record._fields:
                value = record[field_name]
                if isinstance(value, (int, float)) and value > 0:
                    return value
        return 0

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
        value = self._quantity_from_fields(record)
        if value:
            return value
        total = 0.0
        for field_name in self._LINE_FIELDS:
            field = record._fields.get(field_name)
            if not field or field.type not in ('one2many', 'many2many'):
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
            # exists() on the whole recordset costs one query. Calling it per
            # record inside filtered() costs one query per lot. An empty
            # selection is honoured: it must not fall back to every candidate.
            return self.lot_ids.exists()

        active_model = (self.env.context.get('active_model')
                        or self.active_model_id.model)
        active_ids = self.env.context.get('active_ids') or []
        if active_model and active_model in self.env:
            objects = self.env[active_model].browse(active_ids).exists()
            # A template can only render records of its own model. Returning
            # them anyway would make the preview promise labels that the base
            # module then refuses to print.
            if objects and objects._name != self.label_id.model_id.model:
                return objects.browse()
            return objects
        return self.env['stock.lot'].browse()

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

        # Persist the target model on the wizard record. The view-level
        # domain on label_id reads the `model` (related) field of this record;
        # it cannot use the open context, which the web client drops when it
        # computes a many2one dropdown's domain via fields_get.
        effective_model = self._effective_model()
        if effective_model and 'active_model_id' in fields_list and not result.get('active_model_id'):
            ir_model = self.env['ir.model'].search([('model', '=', effective_model)], limit=1)
            if ir_model:
                result['active_model_id'] = ir_model.id

        # Keep the label auto-selection consistent with the (possibly
        # restricted) domain: only templates bound to an action menu are
        # eligible, so never pre-fill a template the user cannot see.
        if 'label_id' in fields_list:
            labels = self.env['printing.label.zpl2'].search(self._label_domain())
            if len(labels) == 1:
                result['label_id'] = labels.id
            else:
                result.pop('label_id', None)
        else:
            labels = self.env['printing.label.zpl2'].browse(result.get('label_id') or [])

        # 只有 stock.lot 类型的标签模板才需要批次/序列号。否则（例如产品标签）
        # 这一步的深递归会被白白执行，每打开一次向导都要遍历库存流水。
        target_labels = self.env['printing.label.zpl2'].browse(
            result.get('label_id') or labels.ids)
        if target_labels and 'stock.lot' in target_labels.model_id.mapped('model'):
            active_model = self.env.context.get('active_model')
            active_ids = self.env.context.get('active_ids') or []
            # Collect serials from any model that references them, not just
            # direct lot fields and related stock move lines on any model.
            # Everything reachable is a candidate; only lots attached to the
            # current records are preselected.
            lots, preselected_lots = self._collect_lots(active_model, active_ids)
            if lots:
                if 'available_lot_ids' in fields_list:
                    result['available_lot_ids'] = [(6, 0, lots.ids)]
                if 'lot_ids' in fields_list:
                    result['lot_ids'] = [(6, 0, preselected_lots.ids)]

        # The ZPL printer in the user profile takes precedence over the
        # generic wizard's "only one printer" auto-selection. The field comes
        # from mrp_zpl_label_print, which is no longer a dependency, so only
        # use it when that module is installed; otherwise fall back to the
        # base wizard's default printer selection.
        if (
            'printer_id' in fields_list
            and 'zpl_printer_id' in self.env.user._fields
            and self.env.user.zpl_printer_id
        ):
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
            # Merge every label of the same record into a single print job
            # instead of generating and sending one ZPL document per label.
            for _key, entries in groupby(plan, key=lambda item: tuple(item[0].ids)):
                count = sum(item[1] for item in entries)
                self.label_id.print_label(
                    self.printer_id, entries[0][0], page_count=count)
                printed += count
        except UserError:
            raise
        except Exception as e:
            _logger.exception(
                'Enhanced ZPL label printing failed after %s label(s)', printed)
            raise UserError(
                _('Label printing failed after %(printed)s label(s) were sent: %(error)s',
                  printed=printed, error=e)) from e

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Printing Complete'),
                'message': _('Successfully printed %d label(s).', printed),
                'type': 'success',
                'sticky': False,
            },
        }
