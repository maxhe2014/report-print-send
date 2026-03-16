{
    'name': 'Repair Order ZPL Label Print',
    'version': '17.0.1.0.0',
    'category': 'Maintenance',
    'summary': 'ZPL Label Printing for Repair Orders',
    'description': """
        Add ZPL label printing functionality to Repair Orders
        Integrates with report-print-send module for ZPL printing
        
        Features:
        - ZPL label printing for Repair Orders
        - ZPL label printing for Stock Move Lines
        - ZPL label printing wizard with template selection
        - User default printing configuration
        - Print button on repair order form view
    """,
    'depends': ['repair', 'printer_zpl2', 'mrp_zpl_label_print'],
    'data': [
        'security/ir.model.access.csv',
        'views/repair_order_views.xml',
        'wizards/print_repair_zpl_label_wizard_views.xml',
    ],
    'i18n': [
        'i18n/zh_CN.po',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}