from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'
    
    def name_get(self):
        """Override name_get to display product name"""
        result = []
        for line in self:
            # Only display product name if available
            if line.product_id:
                # Use only the product name, no other information
                name = line.product_id.name
            else:
                # Fallback to original behavior if no product
                name = super(StockMoveLine, line).name_get()[0][1]
            result.append((line.id, name))
        return result