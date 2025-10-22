{
    'name': "Créditos",
    'summary': "Solicituds de créditos",
    'description': """Modulo para gestionar la asignación de contratos a clientes en el sistema.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'clientes', 'contratos', 'predios', 'ventas'],
    'data': [
        'reports/solcredito_report.xml',
        'views/solcredito.xml',
        'views/solcredito_button_print.xml',
        #'views/cxc_inherit_creditos.xml',
        'data/seq_code.xml',
        'data/cron_saldos.xml',
        'views/edocta.xml',
    ],
    'installable': True,
    'application': True,
}