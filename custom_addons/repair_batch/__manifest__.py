{
    'name': 'Repair Batch Management',
    'version': '1.0',
    'depends': ['sale', 'stock', 'project'],
    'data': [
        'security/ir.model.access.csv',
        'data/stock_location.xml',
        'views/repair_batch_views.xml',
        'views/sale_order.xml',
    ],
    'installable': True,
    'application': True,
}