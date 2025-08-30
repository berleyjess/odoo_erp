# -*- coding: utf-8 -*-
{
    "name": "Sucursales",
    "version": "1.0.0",
    "summary": "Catálogo reutilizable de sucursales",
    "author": "Grupo Safinsa",
    "category": "Tools",
    "depends": ["base","localidades","empresas"],
    "data": [
        #'security/ir.model.access.csv',
        "data/sequence.xml",
        "views/empresa_inherit.xml",
        "views/sucursal.xml",
    ],
    "application": True,
    "installable": True,
}
