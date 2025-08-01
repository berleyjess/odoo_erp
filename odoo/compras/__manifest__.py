{
    'name': 'Compras',
    'version': '1.0',
    'category': 'Purchases',
    'summary': 'Module to manage purchase details',
    'description': """
        This module provides functionalities to manage and track purchase details in Odoo.
    """,
    'author': 'Grupo Safinsa',
    'depends': ['base', 'proveedores'],
    'data': [
        'views\compra.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}