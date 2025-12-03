# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .base_print_mixin import BasePrintMixin
import logging

_logger = logging.getLogger(__name__)


class RepairOrder(models.Model, BasePrintMixin):
    _inherit = 'repair.order'

    def action_repair_end(self):
        """Override the repair end button to automatically print labels with priority:
        1. Product-level ZPL configuration (highest priority)
        2. User-level ZPL configuration (fallback)"""
        result = super().action_repair_end()
        
        # If the return value is a dictionary (wizard), it means user confirmation is needed,
        # but we still need to ensure label printing is triggered
        # Regardless of the return value, we should attempt to trigger label printing
        self._trigger_zpl_label_printing()
        
        return result
    
    def action_repair_done(self):
        """Override the repair done method to automatically print labels"""
        result = super().action_repair_done()
        
        # Ensure label printing is also triggered when repair is completed
        self._trigger_zpl_label_printing()
        
        return result
    
    def _trigger_zpl_label_printing(self):
        """Core logic for triggering ZPL label printing"""
        try:
            # Get lots from repair operations
            lot_ids = self.move_ids.move_line_ids.lot_id
            if not lot_ids:
                # If no operations with lots, check the main product lot
                if self.lot_id:
                    lot_ids = self.lot_id
                else:
                    return
            
            # Priority 1: Check product-level ZPL configuration
            product_template = self.product_id.product_tmpl_id
            if product_template.zpl_label_template_id:
                # Product has ZPL configuration, use it
                self._print_labels_with_product_config(product_template, lot_ids)
                return
            
            # Priority 2: Check user-level ZPL configuration (fallback)
            user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
            if user_config and user_config.active and user_config.trigger_repair_order:
                if user_config.label_template_id:
                    # Use user configuration only if trigger is enabled and template exists
                    user_config.action_auto_print_repair_labels(self.id)
                else:
                    _logger.warning(f"User {user_config.user_id.name} has enabled repair trigger but no label template is configured")
        except Exception as e:
            _logger.error(f"Automatic ZPL label printing failed (Repair Order {self.name}): {e}")
            # Do not interrupt the normal flow, only log the error
    
    def _print_labels_with_product_config(self, product_template, lot_ids):
        """Print labels using product-level ZPL configuration for repair orders"""
        # Get printer (with fallback)
        printer = self._get_printer_with_fallback()

        # Validate printer
        if not printer:
            raise UserError(_("No printer available. Please configure a printer."))
        
        # Print each lot with product configuration
        label_template = product_template.zpl_label_template_id
        
        # Determine copies per label: if product has specific value, use it; otherwise use user config or default
        if product_template.zpl_copies_per_label is not None and product_template.zpl_copies_per_label is not False:
            copies_per_label = product_template.zpl_copies_per_label
        else:
            # Fallback to user configuration
            user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
            if user_config and user_config.active and user_config.copies_per_label:
                copies_per_label = user_config.copies_per_label
            else:
                copies_per_label = 1
        
        for lot in lot_ids:
            for i in range(copies_per_label):
                label_template.print_label(printer, lot)
    
    

    def action_open_repair_zpl_label_wizard(self):
        """Directly print ZPL labels for repair orders without wizard"""
        self.ensure_one()
        
        # Get lots from repair operations (move lines)
        lot_ids = self.move_ids.move_line_ids.lot_id
        if not lot_ids and self.lot_id:
            lot_ids = self.lot_id
        
        if not lot_ids:
            raise UserError(_('No lots/serial numbers found for this repair order.'))
        
        # Get user configuration
        user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
        if not user_config or not user_config.active:
            raise UserError(_('No active user configuration found for ZPL label printing.'))
        
        # Determine printer to use
        printer = user_config.printer_id
        if not printer:
            # Fallback to user's default ZPL printer
            printer = self.env.user.zpl_printer_id
        
        if not printer:
            raise UserError(_('No printer configured for ZPL label printing.'))
            
        if not user_config.label_template_id:
            raise UserError(_('No label template configured for ZPL label printing.'))
        
        # Print labels
        success_count = 0
        error_messages = []
        
        for lot in lot_ids:
            try:
                # Print specified number of copies
                for i in range(user_config.copies_per_label):
                    user_config.label_template_id.print_label(printer, lot)
                success_count += 1
            except Exception as e:
                error_message = _('Failed to print label for lot %s: %s') % (lot.name, str(e))
                error_messages.append(error_message)
                _logger.error(error_message)
        
        # Show result notification
        message_parts = []
        if success_count > 0:
            message_parts.append(_('Successfully printed %d labels') % success_count)
        
        if error_messages:
            message_parts.append(_('%d labels failed to print') % len(error_messages))
        
        if message_parts:
            message_type = 'warning' if error_messages else 'success'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Print Labels'),
                    'message': '\n'.join(message_parts),
                    'sticky': True,
                    'type': message_type,
                }
            }
        
        return {'type': 'ir.actions.act_window_close'}