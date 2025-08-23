{
    'name': "Contratos",
    'summary': "Contratos agrícolas",
    'description': """Contratos agrícolas a clientes con gestión de ciclos y cultivos.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'limiteinsumos', 'ciclos', 'cultivos', 'cargosdetail'],
    'data': [
        'views/contrato.xml',
    ],
    'installable': True,
    'application': True,
}

