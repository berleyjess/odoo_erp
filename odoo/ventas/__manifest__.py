{
    'name': "Ventas",
    'summary': "Ventas",
    'description': """Mi primera app en Odoo con VS Code""",
    'author': "jberley",
    'version': '1.0',
    'depends': ['base', 'clientes', 'contratos'],
    'data': [
        'views/venta.xml',
    ],
    'installable': True,
    'application': True,
}


