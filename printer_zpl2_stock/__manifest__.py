# Copyright (C) 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Printer ZPL II - Stock Integration",
    "version": "19.0.1.0.0",
    "category": "Printer",
    "summary": "Use custom ZPL II labels for lot/SN and package printing in stock",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/report-print-send",
    "license": "AGPL-3",
    "depends": ["printer_zpl2", "stock", "base_report_to_label_printer"],
    "data": [
        "views/product_template_views.xml",
        "views/stock_picking_type_views.xml",
    ],
    "installable": True,
}
