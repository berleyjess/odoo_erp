{
    'name': "Empresas",
    'summary': "Empresas",
    'description': """Modulo para gestionar empresas y sus datos.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'mx_cfdi_core'],
    'data': [
        #'security/ir.model.access.csv',
        'data/seq_code.xml',
        'views/empresa.xml',
        'views/res_company_cfdi_views.xml'
    ],
    'installable': True,
    'application': True,
}

