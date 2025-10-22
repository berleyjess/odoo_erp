{
    'name':'Transacciones',
    'description':"""Detalle de transacciones de Compras/Ventas""",
    'author': 'Grupo Safinsa',
    'depends':['base', 'productos', 'sucursales'],
    'version': '1.0',
    'data':[
        'views/transaccion.xml',

    ],
    'installable': True,
    'application': True,
    'auto_install': True,
}