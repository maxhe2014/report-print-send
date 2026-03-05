{
    'name': 'Stock Picking ZPL Label Print',
    'version': '17.0.1.0.0',
    'category': 'Inventory',
    'summary': 'ZPL Label Printing for Stock Pickings',
    'description': """
        Add ZPL label printing functionality to Stock Pickings
        Integrates with report-print-send module for ZPL printing
        
        Features:
        - ZPL label printing for Stock Pickings
        - ZPL label printing wizard with template selection
        - User default printing configuration
        - Print button on picking form view
    """,
    'depends': ['stock', 'printer_zpl2'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking_views.xml',
        'wizards/print_picking_zpl_label_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}