{
    'name': "Clientes",
    'summary': "Catálogo de clientes",
    'description': """Mi primera app en Odoo con VS Code""",
    'author': "jberley",
    'version': '1.0',
    'depends': ['base', 'localidades'],
    'data': [
        'views/cliente.xml',
        'data/seq_code.xml',
        'data/c_regimenfiscal.csv',
    ],
    'installable': True,
    'application': True,
}

