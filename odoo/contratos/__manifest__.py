{
    'name': "Contratos",
    'summary': "Contratos agrícolas",
    'description': """Contratos agrícolas a clientes con gestión de ciclos y cultivos.""",
    'author': "jberley",
    'version': '1.0',
    'depends': ['base', 'limiteinsumos', 'ciclos', 'cultivos'],
    'data': [
        'views/contrato.xml',
    ],
    'installable': True,
    'application': True,
}

