# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _
import logging

_logger = logging.getLogger(__name__)


class BasePrintMixin(models.AbstractModel):
    _name = 'base.print.mixin'
    _description = 'Base Print Mixin'

    def _get_printer_with_fallback(self):
        """Get printer with fallback logic: user default printer -> first active printer"""
        # Priority 1: User's default ZPL printer
        if self.env.user.zpl_printer_id and self.env.user.zpl_printer_id.status == 'online':
            return self.env.user.zpl_printer_id
            
        # Priority 2: User's default printer
        if self.env.user.printing_printer_id and self.env.user.printing_printer_id.status == 'online':
            return self.env.user.printing_printer_id

        # Priority 3: First active printer
        printer = self.env['printing.printer'].search([('active', '=', True)], limit=1)
        if printer:
            return printer
        
        # No printer found
        return None
        
    def _print_labels(self, printer, label_template, records, copies_per_label=1):
        """Print labels for given records
        
        Args:
            printer: printing.printer record
            label_template: printing.label.zpl2 record
            records: records to print labels for
            copies_per_label: number of copies per label
            
        Returns:
            dict: {'success_count': int, 'error_messages': list}
        """
        success_count = 0
        error_messages = []
        
        try:
            # Ensure copies_per_label is an integer
            copies_per_label = int(copies_per_label)
            
            # 批量生成ZPL数据
            zpl_content = b""
            for record in records:
                try:
                    for i in range(copies_per_label):
                        # 生成单个标签的ZPL数据
                        label_content = label_template._generate_zpl2_data(record)
                        zpl_content += label_content
                    success_count += 1
                except Exception:
                    error_messages.append(f"Failed to generate label for {record._name} {record.name}")
            
            # 一次性发送所有标签
            if zpl_content:
                try:
                    printer.print_document(None, zpl_content, format='raw')
                except Exception:
                    error_messages.append("Failed to send print job")
        except Exception:
            error_messages.append("Unexpected error during label printing")
        
        return {'success_count': success_count, 'error_messages': error_messages}