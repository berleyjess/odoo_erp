{
    'name': "Productos",
    'summary': "Catálogo de productos",
    'description': """Mi primera app en Odoo con VS Code""",
    'author': "jberley",
    'version': '1.0',
    'depends': ['base'],
    'data': [
        'views/productos.xml',
        'views/codigoproducto.xml',
        'data/seq_code.xml',
        'data/codigoproductosat.csv',
    ],
    'installable': True,
    'application': True,
}

