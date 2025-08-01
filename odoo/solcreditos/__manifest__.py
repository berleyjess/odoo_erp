{
    'name': "Solicitudes de Créditos",
    'summary': "Solicituds de créditos",
    'description': """Modulo para gestionar la asignación de contratos a clientes en el sistema.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'clientes', 'contratos', 'predios'],
    'data': [
        'views/solcredito.xml',
        'data/seq_code.xml'
    ],
    'installable': True,
    'application': True,    
}