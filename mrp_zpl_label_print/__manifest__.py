{
    'name': 'MRP ZPL Label Print',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'ZPL Label Printing for Manufacturing Orders and Lots/Serials',
    'description': """
        Add ZPL label printing functionality to Manufacturing Orders and Lots/Serials
        Integrates with report-print-send module for ZPL printing
        
        Features:
        - ZPL label printing for Manufacturing Orders
        - ZPL label printing for Lots/Serials
        - User default printing configuration
        - Automatic label printing on manufacturing completion
    """,
    'depends': ['mrp', 'stock', 'printer_zpl2'],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_production_views.xml',
        'views/stock_lot_views.xml',
        'views/print_mrp_zpl_label_wizard_user_views.xml',
        'wizards/print_mrp_zpl_label_wizard_views.xml',
        'wizards/print_zpl_label_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}