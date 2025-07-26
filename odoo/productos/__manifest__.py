{
    'name': "Productos",
    'summary': "Catálogo de productos",
    'description': """Modulo para la gestión de productos y sus códigos.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base'],
    'data': [
        'views/productos.xml',
        'views/codigoproducto.xml',
        'data/seq_code.xml',
        'data/productos.codigoproductosat.csv',
    ],
    'installable': True,
    'application': True,
}

