{
    'name': 'Contabilidad',
    'version': '1.0',
    'depends': ['base'],
    'author': 'Grupo Safinsa',
    'depends': ['base', 'movcuentas'],
    'data': [
        'views/contabilidad_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}