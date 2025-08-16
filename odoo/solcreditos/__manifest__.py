{
    'name': "Solicitudes de Créditos",
    'summary': "Solicituds de créditos",
    'description': """Modulo para gestionar la asignación de contratos a clientes en el sistema.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'clientes', 'contratos', 'predios', 'cuentasxcobrar'],
    'data': [
        'reports/solcredito_report.xml',
        'views/solcredito_button_print.xml',
        'views/solcredito.xml',
        'views/cxc_inherit_solcreditos.xml',
        'data/seq_code.xml',

    ],
    'installable': True,
    'application': True,
}