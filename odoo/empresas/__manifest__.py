{
    'name': "Empresas",
    'summary': "Empresas",
    'description': """Modulo para gestionar empresas y sus datos.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base'],
    'data': [
        #'security/ir.model.access.csv',
        'data/seq_code.xml',
        'views/empresa.xml',
    ],
    'installable': True,
    'application': True,
}

