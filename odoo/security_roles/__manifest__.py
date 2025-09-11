# security_roles/__manifest__.py
{
    'name': "Security Roles",
    'summary': "Gestión de roles de seguridad",
    'description': """Este módulo permite gestionar roles de seguridad para usuarios en Odoo, facilitando y agrupando la asignación de permisos y grupos de usuarios.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': [
        "base",
        "empresas",
        "sucursales",
        "productos",
        "clientes",
        "creditos",
        "transacciones",
        "ventas",
        "contactos",     # contactos.contacto
        #"personas",       # persona.persona
        "localidades",   # localidades.localidad
        "contratos",     # contratos.contrato
        "stocks",         # stocks.stock
    ],
    'data': [
        "security/roles_groups.xml",         # 1) grupos
        "security/roles_record_rules.xml",   # 2) reglas por empresa/sucursal
        "security/ir.model.access.csv",      # 3) ACL (csv SIEMPRE después de los grupos)
    ],
    'installable': True,
    'application': True,
}


