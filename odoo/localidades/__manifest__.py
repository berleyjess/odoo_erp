{
    'name': "Localidades",
    'summary': "Localidades y Ciudades",
    'description': """Modulo para gestionar localidades y ciudades.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base'],
    'data': [
        'views/localidad.xml',
	    'data/localidades.municipio.csv',
    ],
    'installable': True,
    'application': True,
    'auto_install': True,
}

