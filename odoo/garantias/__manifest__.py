{
    'name': "Garantías",
    'summary': "Garantias de los clientes",
    'description': """Garantías de los clientes para la parte de creditos""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'clientes'],
    'data': [
        'views/garantia_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': True,
}