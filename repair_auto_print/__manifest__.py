# Copyright 2026 宁波企智信息科技有限公司
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

{
    "name": "Repair Auto Print",
    "summary": "Automatically print repair documents and labels on completion",
    "version": "19.0.1.1.1",
    "category": "Manufacturing",
    "author": "宁波企智信息科技有限公司, Odoo Community Association (OCA)",
    "website": "https://www.qz-technology.cn",
    "license": "LGPL-3",
    "depends": ["repair", "printer_zpl2", "base_report_to_label_printer"],
    "data": [
        "views/product_template_views.xml",
        "views/stock_picking_type_views.xml",
    ],
    "installable": True,
    "application": False,
}
