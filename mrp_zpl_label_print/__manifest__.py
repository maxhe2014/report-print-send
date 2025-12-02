{
    'name': 'MRP ZPL Label Print',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'ZPL Label Printing for Manufacturing Orders',
    'description': """
        Add ZPL label printing functionality to Manufacturing Orders
        Integrates with report-print-send module for ZPL printing
    """,
    'depends': ['mrp', 'lot_zpl_label_print'],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_production_views.xml',
        'views/print_mrp_zpl_label_wizard_user_views.xml',
        'wizards/print_mrp_zpl_label_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}