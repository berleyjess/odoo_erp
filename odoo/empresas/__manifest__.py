{
    'name': "Empresas",
    'summary': "Empresas",
    'description': """Mi primera app en Odoo con VS Code""",
    'author': "jberley",
    'version': '1.0',
    'depends': ['base'],
    'data': [
        'views/empresa.xml',
        'data/seq_code.xml',
    ],
    'installable': True,
    'application': True,
}

