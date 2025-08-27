{
    'name': "Contactos",
    'summary': "Contactos de clientes y proveedores",
    'description': "Módulo para gestionar contactos genéricos.",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'personas'],
    'data': [
        'views/phone_lookup_wizard_view.xml',
        'views/contacto.xml',
        'views/persona_link_contacts.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
