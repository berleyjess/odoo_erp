{
    'name': "Bodegas",
    'summary': "Bodegas de las empresas.Almacen físico de productos.",
    'description': """Este módulo permite gestionar las bodegas de las empresas dentro del sistema. Facilita la creación, edición y visualización de bodegas, así como la asociación de estas con las empresas correspondientes.""",
    'author': "Grupo Safinsa",
    'version': '1.0',
    'depends': ['base', 'empresas'],
    'data': [
        'views/bodega.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': True,
}