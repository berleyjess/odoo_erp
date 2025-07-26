{
    'name': 'Límite de Insumos',
    'version': '1.0',
    'summary': 'Gestiona los límites de insumos por contrato agrícola',
    'author': 'safinsa',
    'description': """
        Este módulo gestiona los límites de insumos por contrato agrícola.
    """,
    'depends': ['base', 'productos'],
    'data': [
        'views\limiteinsumos.xml',
    ],
    'installable': True,
    'application': False,
}