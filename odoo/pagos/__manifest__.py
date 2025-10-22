{
    'name': "Pagos",
    'summary': """Modulo de Pagos""",
    'description': """Modulo de Pagos""",
    'author': "Grupo Safinsa",
    'depends': ['base', 'clientes', 'creditos', 'pagosdetail', 'ventas', 'cargosdetail'],
    'data': [
        'views/pago.xml',
        'views/cargarventas.xml',
        'views/cargarcargos.xml',
        'data/seq_code.xml'
    ],
    'assets':{
        'web.assets_backend': [
            'pagos/static/src/scss/status_badge.css',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,

}