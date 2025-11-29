{
    'name': "Pruebas",
    'summary': "Simple test module",
    'description': """Modulo de pruebas.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base','permisos'],
    'data': [
        'security/permisos_pruebas_security.xml',
        'views/pruebapersona.xml',
        'reports/report_templates.xml',
        'reports/report_actions.xml',
    ],
    'installable': True,
    'application': True,
}

