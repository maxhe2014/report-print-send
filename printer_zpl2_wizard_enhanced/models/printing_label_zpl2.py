# -*- coding: utf-8 -*-
from odoo import api, models


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
        Action = self.env['ir.actions.act_window']
        for label in self:
            if label.action_window_id:
                continue
            action = Action.search([
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
        """Detach only these labels; never delete the shared action itself."""
        # Keep the action alive so other labels of the same model stay bound.
        # An action with no labels left is harmless: the binding is what makes
        # the "Print Label" menu entry appear, and the wizard domain below
        # hides all labels once they are detached.
        self.write({'action_window_id': False})
        return True
