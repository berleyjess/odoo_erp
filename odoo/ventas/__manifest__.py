{
    'name': "Ventas",
    'summary': "Ventas",
    'description': """Módulo para gestionar ventas de artículos""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'clientes', 'solcreditos', 'detalleventas'],
    'data': [
        'views/venta.xml',
    ],
    'installable': True,
    'application': True,
}


