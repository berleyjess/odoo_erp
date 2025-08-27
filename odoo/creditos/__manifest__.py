{
    'name': "Créditos",
    'summary': "Solicituds de créditos",
    'description': """Modulo para gestionar la asignación de contratos a clientes en el sistema.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'clientes', 'contratos', 'predios'],
    'data': [
        'reports/solcredito_report.xml',
        #'views/credito_button_print.xml',
        'views/solcredito.xml',
        #'views/cxc_inherit_creditos.xml',
        'data/seq_code.xml',
        'views/edocta.xml',
    ],
    'installable': True,
    'application': True,
}