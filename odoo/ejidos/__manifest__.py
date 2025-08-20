{
    'name': "Ejidos",
    'summary': "Ejidos de localidades",
    'description': """Ejidos dentro de localidades, este modulo permite crear y gestionar ejidos asociados a localidades.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base',"localidades"],
    'data': [
        'views/ejido_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': True,
}