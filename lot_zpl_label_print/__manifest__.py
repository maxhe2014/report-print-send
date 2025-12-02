{
    'name': '批次ZPL标签打印',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': '为批次/序列号提供ZPL标签打印功能，支持多种标签模板选择',
    'description': """
        批次ZPL标签打印模块
        ===================
        
        为Odoo的批次/序列号管理提供灵活的ZPL标签打印功能，支持：
        - 多种标签模板选择
        - 快速打印和选择模板打印两种模式
        - 批量打印功能
        - 每标签多份打印
        """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['stock', 'printer_zpl2'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_lot_views.xml',
        'wizards/print_zpl_label_wizard_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}