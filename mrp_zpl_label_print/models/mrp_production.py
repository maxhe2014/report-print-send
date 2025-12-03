from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def button_mark_done(self):
        """Override the mark as done button to automatically print labels with priority:
        1. Product-level ZPL configuration (highest priority)
        2. User-level ZPL configuration (fallback)"""
        result = super().button_mark_done()
        
        try:
            # Get lots from finished product move lines
            lot_ids = self.move_finished_ids.mapped('move_line_ids.lot_id')
            if not lot_ids:
                return result
            
            # Priority 1: Check product-level ZPL configuration
            product_template = self.product_id.product_tmpl_id
            if product_template.zpl_label_template_id:
                # Product has ZPL configuration, use it
                self._print_labels_with_product_config(product_template, lot_ids)
                return result
            
            # Priority 2: Check user-level ZPL configuration (fallback)
            user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
            if user_config and user_config.active and user_config.label_template_id:
                # Use user configuration
                user_config.action_auto_print_labels(self.id)
        except Exception as e:
            _logger.error(f"自动打印ZPL标签失败 (制造订单 {self.name}): {e}")
            # 不中断正常流程，只记录错误
        
        return result
    
    def _print_labels_with_product_config(self, product_template, lot_ids):
        """Print labels using product-level ZPL configuration"""
        # Get printer with fallback logic
        printer = self._get_printer_with_fallback()
        
        if not printer:
            # No printer available, skip printing
            return
        
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
    
    def _get_printer_with_fallback(self):
        """Get printer with fallback logic: user ZPL printer -> user default printer -> first active printer"""
        # Priority 1: User's default ZPL printer
        if self.env.user.zpl_printer_id:
            return self.env.user.zpl_printer_id
        
        # Priority 2: User's default printer
        if self.env.user.printing_printer_id:
            return self.env.user.printing_printer_id
        
        # Priority 3: First active printer
        printer = self.env['printing.printer'].search([('active', '=', True)], limit=1)
        return printer

    def action_open_mrp_zpl_label_wizard(self):
        """Open the ZPL label printing wizard for manufacturing orders"""
        self.ensure_one()
        
        # Get the wizard view
        view = self.env.ref('mrp_zpl_label_print.print_mrp_zpl_label_wizard_form')
        
        return {
            'name': 'Print ZPL Labels for Manufacturing Order',
            'type': 'ir.actions.act_window',
            'res_model': 'print.mrp.zpl.label.wizard',
            'view_mode': 'form',
            'view_id': view.id,
            'target': 'new',
            'context': {
                'default_production_id': self.id,
                'default_lot_ids': [(6, 0, self.move_finished_ids.mapped('move_line_ids.lot_id').ids)] if self.move_finished_ids.mapped('move_line_ids.lot_id') else False,
            },
        }