{
    'name': "Proveedores",
    'summary': "Cartera de Proveedores",
    'description': "Listado general de Proveedores y contactos (rol sobre Personas).",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'contactos', 'personas'],
    'data': [
        'views/persona_link.xml',
        'views/helpers.xml',
        'views/proveedor.xml',
        'views/rfc_lookup_wizard_view.xml',
        'data/seq_code.xml', # Carga secuencia, luego vistas. Si dejas el wizard en archivo separado.
    ],
    'installable': True,
    'application': True,
}
