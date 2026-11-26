# Copyright (C) 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

from odoo import fields, models


class PrintingLabelZpl2(models.Model):
    """Make the 'Action' menu toggle act on a single label template.

    The base ``printer_zpl2`` implementation works at model level:

    * ``create_action`` associates every label of the same model at once;
    * ``unlink_action`` deletes the shared action, which silently detaches
      every other label of that model.

    Both are surprising when several templates exist for one model. We keep
    the standard action binding (needed for the form's "Print Label" menu
    entry) but scope the add/remove operations to the current record only.

    The model also carries the printing options that used to live in the
    upstream addon: print darkness, the label default printer and the
    per-user printer overrides.
    """

    _inherit = 'printing.label.zpl2'

    darkness = fields.Integer(
        string="Print Darkness",
        default=0,
        help="Control the print darkness from -30 (lightest) to 30 "
        "(darkest). 0 is the default value.",
    )
    default_printer_id = fields.Many2one(
        comodel_name="printing.printer",
        string="Default Printer",
        help="Default printer used for automatic printing of this label. "
        "Takes priority over the user's default label printer, but is "
        "overridden by a per-user printer configured in the User Printers "
        "list below.",
    )
    user_action_ids = fields.One2many(
        comodel_name="printing.label.zpl2.user.action",
        inverse_name="label_id",
        string="User Printers",
        help="Per-user printer overrides for this label. If a user has a "
        "record here with an active printer, that printer takes priority "
        "over the label's default printer and the user's default label "
        "printer.",
    )

    def _get_component_data(self, record, component, eval_args):
        """Expose ``env`` to the label data expressions."""
        eval_args = dict(eval_args, env=record.env)
        return super()._get_component_data(record, component, eval_args)

    def _generate_zpl2_data(self, record, page_count=1, **extra):
        data = super()._generate_zpl2_data(record, page_count=page_count, **extra)
        if self.darkness and not extra.get("labelary_emul"):
            # The base generator returns the ZPL stream as bytes.
            if isinstance(data, bytes):
                data = data.replace(
                    b"^XA", b"^XA^MD" + str(self.darkness).encode()
                )
            elif isinstance(data, str):
                data = data.replace("^XA", f"^XA^MD{self.darkness}")
        return data

    def create_action(self):
        """Bind only the labels explicitly requested to the model's action."""
        action_model = self.env['ir.actions.act_window']
        for label in self:
            if label.action_window_id:
                continue
            action = action_model.search([
                ('binding_model_id', '=', label.model_id.id),
                ('res_model', '=', 'wizard.print.record.label'),
                ('view_mode', '=', 'form'),
                ('binding_type', '=', 'action'),
            ], limit=1)
            if not action:
                action = self.new_action(label.model_id.id)
            label.action_window_id = action
        return True

    def unlink_action(self):
        """Detach these labels and delete the action once it is unused."""
        # The action is shared by every label of the model. Once no template is
        # bound to it anymore, it has to be removed too: otherwise the model's
        # Action menu keeps showing "Print Label" with no selectable template.
        actions = self.mapped('action_window_id')
        self.write({'action_window_id': False})
        for action in actions:
            if not self.search_count([('action_window_id', '=', action.id)]):
                action.unlink()
        return True
