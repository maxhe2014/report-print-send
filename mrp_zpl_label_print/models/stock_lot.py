from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockLot(models.Model):
    _inherit = 'stock.lot'
    
    def action_open_print_zpl_label_wizard(self):
        """
        Open the ZPL label printing wizard for flexible label selection
        """
        return {
            'name': _('打印ZPL标签'),
            'type': 'ir.actions.act_window',
            'res_model': 'print.zpl.label.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_ids': [(6, 0, self.ids)],
                'active_model': 'stock.lot',
                'active_ids': self.ids,
                'active_id': self.id if len(self) == 1 else False,
            }
        }
    
    def action_print_default_zpl_label(self):
        """Direct print functionality for stock lots with user configuration support"""
        self.ensure_one()
        
        # Get user's default configuration
        user_config = self.env['print.mrp.zpl.label.wizard.user'].get_user_config()
        
        # If user has config and trigger is disabled, skip printing
        if user_config and not user_config.trigger_stock_lot:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Printing Skipped"),
                    'message': _("Label printing is disabled for stock lots in your configuration"),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Get user's default settings or fall back to system defaults
        if user_config and user_config.label_template_id and user_config.printer_id:
            label_template = user_config.label_template_id
            printer = user_config.printer_id
            copies = user_config.copies_per_label or 1
        else:
            # Fall back to system defaults
            label_template = self.env['printing.label.zpl2'].search([
                ('model_id.model', '=', 'stock.lot'),
                ('active', '=', True)
            ], order='name', limit=1)
            
            if not label_template:
                raise UserError(_('未找到适用于批次/序列号的标签模板，请先创建标签模板。'))
                
            printer = self.env['printing.printer'].search([], limit=1)
            copies = 1
            
        if not printer:
            raise UserError(_('未找到可用的打印机，请先配置打印机。'))
            
        # Print the label (possibly multiple copies)
        for i in range(copies):
            label_template.print_label(printer, self)
        
        # Return success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Success"),
                'message': _("Label printed successfully"),
                'type': 'success',
                'sticky': False,
            }
        }