{
    'name': "Accesos",
    'summary': "Accesos de Usuarios a empresas, sucursales y bodegas",
    'description': """Este módulo permite gestionar los accesos de usuarios a diferentes empresas, sucursales y bodegas dentro del sistema. Facilita la asignación y control de permisos para asegurar que los usuarios solo puedan acceder a la información y funcionalidades relevantes para su rol y responsabilidades.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'mail','empresas','bodegas','permisos'],
    'data': [
        'data/sequence.xml',
        'views/acceso.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': True,
}