# Copyright (C) 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

{
    "name": "Stock/MRP Auto Print",
    "version": "17.0.1.0.0",
    "category": "Printer",
    "summary": "Use custom ZPL II labels for lot/SN and package printing in stock",
    "author": "metaodoo.com",
    "website": "https://metaodoo.com",
    "license": "OPL-1",
    "depends": [
        "printer_zpl2",
        "printer_zpl2_enhanced",
        "stock",
        "base_report_to_label_printer",
        "mrp",
    ],
    "data": [
        "views/product_template_views.xml",
        "views/stock_picking_type_views.xml",
        "views/mrp_stock_picking_type_views.xml",
    ],
    "installable": True,
}
