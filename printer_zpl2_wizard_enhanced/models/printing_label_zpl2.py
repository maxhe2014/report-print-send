# -*- coding: utf-8 -*-
from odoo import models


class PrintingLabelZpl2(models.Model):
    """Make the 'Action' menu toggle act on a single label template.

    The base ``printer_zpl2`` implementation works at model level:

    * ``create_action`` associates every label of the same model at once;
    * ``unlink_action`` deletes the shared action, which silently detaches
      every other label of that model.

    Both are surprising when several templates exist for one model. We keep
    the standard action binding (needed for the form's "Print Label" menu
    entry) but scope the add/remove operations to the current record only.
    """

    _inherit = 'printing.label.zpl2'

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
