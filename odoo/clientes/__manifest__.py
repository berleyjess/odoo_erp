{
    'name': "Clientes",
    'summary': "Catálogo de clientes",
    'description': """Módulo para gestionar clientes y sus datos fiscales.""",
    'author': "jberley",
    'version': '1.0',
    'depends': ['base', 'localidades'],
    'data': [
        'views/cliente.xml',
        'data/seq_code.xml',
        'data/clientes.c_regimenfiscal.csv',
    ],
    'installable': True,
    'application': True,
}

