{
    'name': 'Repair Batch Management',
    'version': '1.0',
    'depends': ['sale', 'project'],
    'data': [
        'security/ir.model.access.csv',
        'views/repair_batch_views.xml',
    ],
    'installable': True,
    'application': True,
}