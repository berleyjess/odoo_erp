# Módulo Clientes: define secuencia, vistas, wizard RFC y vínculo con Personas.
# Carga de datos: la secuencia 'seq_client_code' y catálogo de régimen fiscal (CSV).
# Depende de 'personas' para delegación (_inherits) y de 'contactos' para O2M de contactos.
{
    'name': "Clientes",
    'summary': "Catálogo de clientes",
    'description': """Módulo para gestionar clientes y sus datos fiscales.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'localidades', 'contactos', 'personas'],
    'license': 'LGPL-3',
    'data': [
        #'security/ir.model.access.csv',
        'data/seq_code.xml',#ir.sequence 'seq_client_code' para campo codigo. :contentReference[oaicite:0]{index=0}

        'views/persona_link_views.xml',
        'views/rfc_lookup_wizard_view.xml',
        'data/clientes.c_regimenfiscal.csv',
        'views/cliente.xml',
    ],
    'installable': True,
    'application': True,
}

