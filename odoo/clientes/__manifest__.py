{
    'name': "Clientes",
    'summary': "Catálogo de clientes",
    'description': """Módulo para gestionar clientes y sus datos fiscales.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'localidades', 'contactos'],
    'data': [
        'data/seq_code.xml',
        'data/clientes.c_regimenfiscal.csv',
        'views/cliente.xml'
    ],
    'installable': True,
    'application': True,
}

