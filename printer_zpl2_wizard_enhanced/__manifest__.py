# Copyright 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

{
    'name': 'Printer ZPL2 Label Print Wizard Enhanced',
    'version': '17.0.6.1.0',
    'category': 'Printer',
    'summary': 'Enhance the generic ZPL label printing wizard with quantity modes and a serial range',
    'author': 'metaodoo.com',
    'website': 'https://metaodoo.com',
    'depends': ['printer_zpl2', 'stock'],
    'data': [
        'views/wizard_print_record_label_views.xml',
    ],
    'license': 'OPL-1',
}
