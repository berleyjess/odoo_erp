{
    'name': "usuarios",
    'summary': "usuarios",
    'description': """Módulo para gestionar usuarios.""",
    'author': "Grupo Safinsa",
    'version': '1.1',
    'depends': ['base', 'empresas', 'sucursales','bodegas'],
    'data': [
        'security/ir.model.access.csv',
        'views/record_rules.xml',
        'views/usuarios.xml',
    ],
    'installable': True,
    'application': True,
}


