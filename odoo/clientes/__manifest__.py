{
    'name': "Clientes",
    'summary': "Catálogo de clientes",
    'description': """Módulo para gestionar clientes y sus datos fiscales.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'localidades', 'contactos', 'personas'],
    'license': 'LGPL-3',
    'data': [
        'data/seq_code.xml',
        'views/persona_link_views.xml',
        'views/rfc_lookup_wizard_view.xml',
        'data/clientes.c_regimenfiscal.csv',
        'views/cliente.xml',
    ],
    'installable': True,
    'application': True,
}

