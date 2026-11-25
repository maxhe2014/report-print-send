# Copyright 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

{
    "name": "Repair Auto Print",
    "summary": "Automatically print repair documents and labels on completion",
    "version": "17.0.1.1.2",
    "category": "Manufacturing",
    "author": "metaodoo.com",
    "website": "https://metaodoo.com",
    "license": "OPL-1",
    "depends": [
        "repair",
        "printer_zpl2",
        "printer_zpl2_wizard_enhanced",
        "base_report_to_label_printer",
    ],
    "data": [
        "views/product_template_views.xml",
        "views/stock_picking_type_views.xml",
    ],
    "installable": True,
    "application": False,
}
