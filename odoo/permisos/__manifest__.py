# -*- coding: utf-8 -*-
{
    "name": "Permisos Seguridad",
    "version": "18.0",
    "summary": "Catálogo de permisos por módulo, rangos y asignaciones por usuario",
    "depends": ["base", "usuarios", "empresas", "sucursales", "bodegas", "accesos"],
    "data": [
        "security/ir.model.access.csv",
        "views/permisos_views.xml",
        "views/permisos_wizard_views.xml",
        "data/permisos_demo.xml",
    ],
    "application": True,
    "installable": True,
    "autoinstall": True,
}
