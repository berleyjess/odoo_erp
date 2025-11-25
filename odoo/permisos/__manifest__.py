# -*- coding: utf-8 -*-
#permisos/__manifest__.py
{
    "name": "Permisos Seguridad",
    "version": "18.0",
    "summary": "Catálogo de permisos por módulo, rangos y asignaciones por usuario",
    "depends": ["base", "usuarios", "empresas", "sucursales", "bodegas"],
    "data": [
        "security/ir.model.access.csv",
        "views/permisos_views.xml",
        "views/permisos_wizard_views.xml",
        "views/apply_security.xml",
        "views/set_context.xml",
        "views/permisos_views_menuids.xml",
        "views/audit_views.xml",
        "data/permisos_demo.xml",
        'data/permisos_security_data.xml',
    ],
    "application": True,
    "installable": True,
}
