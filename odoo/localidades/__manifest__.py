{
    'name': "Localidades",
    'summary': "Localidades y Ciudades",
    'description': """Mi primera app en Odoo con VS Code""",
    'author': "jberley",
    'version': '1.0',
    'depends': ['base'],
    'data': [
        'views/localidad.xml',
	    'data/municipio.csv',
    ],
    'installable': True,
    'application': True,
}

