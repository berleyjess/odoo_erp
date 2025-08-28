# -*- coding: utf-8 -*-
{
    "name": "Stock",
    "version": "1.0.0",
    "summary": "Existencias por sucursal y actualización desde Compras",
    "author": "Grupo Safinsa",
    "category": "Inventory",
    "depends": [
        "base",
        "sucursales",
        #"compras",
        "productos",
    ],
    "data": [
        "views/stock.xml",
        #"views/compra.xml",
    ],
    "application": True,
    "installable": True,
}
