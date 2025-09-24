{
    'name': "Pagos",
    'summary': """Modulo de Pagos""",
    'description': """Modulo de Pagos""",
    'author': "Grupo Safinsa",
    'depends': ['base', 'clientes', 'creditos', 'pagosdetail'],
    'data': [
        'views/pago.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,

}