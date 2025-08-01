{
    'name': "Proveedores",
    'summary': "Cartera de Proveedores",
    'description': """Listado de general de Proveedores y datos de contacto.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'contactos'],
    'data': [
        'views/proveedor.xml',
        'data/seq_code.xml'
    ],
    'installable': True,
    'application': True,
}


