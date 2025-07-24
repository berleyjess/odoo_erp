{
    'name': "Asignacion",
    'summary': "Asignación de contratos a clientes",
    'description': """Mi primera app en Odoo con VS Code""",
    'author': "jberley",
    'version': '1.0',
    'depends': ['base', 'clientes', 'contratos'],
    'data': [
        'views/asignacion.xml',
    ],
    'installable': True,
    'application': True,
}

