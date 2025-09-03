{
    'name': "Ventas",
    'summary': "Ventas",
    'description': """Módulo para gestionar ventas de artículos""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'clientes', 'creditos', 'transacciones','usuarios','mx_cfdi_core','mail',],
    'data': [
        'wizard/cfdi_wizard_views.xml',
        #'security/ir.model.access.csv',
        'reports/venta_report.xml',
        #'views/venta_button_print.xml',
        'data/ir_sequence_ventas.xml',
        #'views/preventa.xml',
        'views/venta.xml',
        #'views/cxc_inherit_ventas.xml',
        
    ],
    'installable': True,
    'application': True,
}


