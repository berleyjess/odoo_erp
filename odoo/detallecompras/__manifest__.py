{
    'name': 'Detalle de Compras',
    'version': '1.0',
    'summary': 'Module to manage purchase details',
    'description': """
        This module provides functionalities to manage and track purchase details in Odoo.
    """,
    'author': 'Grupo Safinsa',
    'depends': ['base','productos'],
    'data': [
        'views\detallecompra.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}