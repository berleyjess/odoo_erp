{
    'name': "Asignacion",
    'summary': "Asignación de contratos a clientes",
    'description': """Modulo para gestionar la asignación de contratos a clientes en el sistema.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'clientes', 'contratos'],
    'data': [
        'views/asignacion.xml',
    ],
    'installable': True,
    'application': True,
}

