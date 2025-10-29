{
    'name': "Créditos",
    'summary': "Crédito",
    'description': """Modulo para gestionar la asignación de Lineas de crédito a clientes en el sistema.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'clientes', 'contratos', 'ventas'],
    'data': [
        'views/garantia.xml',
        'reports/solcredito_report.xml',
        'views/solcredito.xml',
        'views/solcredito_button_print.xml',
        'views/menu_actions.xml',
        'views/predio.xml',
        'data/seq_code.xml',
        'views/cargos.xml',
        'data/cron_saldos.xml',
        'views/edocta.xml',
        'views/entrys.xml'
    ],
    'installable': True,
    'application': True,
}