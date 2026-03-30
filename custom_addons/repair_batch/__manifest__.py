{
    'name': 'Repair Batch Management',
    'version': '1.0',
    'depends': ['sale', 'stock', 'sale_stock', 'repair', 'project'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/stock_location.xml',
        'views/repair_batch_views.xml',
        'views/sale_order.xml',
        'views/repair_profit_views.xml',
    ],
    'installable': True,
    'application': True,
}
