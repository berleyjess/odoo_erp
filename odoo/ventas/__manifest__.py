{
    'name': "Ventas",
    'summary': "Ventas",
    'description': """Módulo para gestionar ventas de artículos""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'clientes', 'solcreditos', 'detalleventas','cuentasxcobrar'],
    'data': [
        'views/venta.xml',
        'views/cxc_inherit_ventas.xml',
    ],
    'installable': True,
    'application': True,
}


