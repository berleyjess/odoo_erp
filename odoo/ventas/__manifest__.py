{
    'name': "Ventas",
    'summary': "Ventas",
    'description': """Módulo para gestionar ventas de artículos""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'clientes', 'solcreditos', 'detalleventas','cuentasxcobrar'],
    'data': [
        'data/ir_sequence_ventas.xml',
        'views/preventa.xml',
        'views/venta.xml',
        'views/cxc_inherit_ventas.xml',
    ],
    'installable': True,
    'application': True,
}


