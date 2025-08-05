# security_roles/__manifest__.py
{
    'name': "Security Roles",
    'summary': "Gestión de roles de seguridad",
    'description': """Este módulo permite gestionar roles de seguridad para usuarios en Odoo, facilitando y agrupando la asignación de permisos y grupos de usuarios.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'ciclos','clientes','ejidos','georeferencias', 'garantias', 'localidades'],
    'data': [
        "security/roles_groups.xml",
        "security/ir.model.access.csv",
    ],
    'installable': True,
    'application': True,
}


