# -*- coding: utf-8 -*-
{
    'name': 'Custom Dashboard',
    'version': '18.0.1.0.0',
    'summary': 'Panel principal personalizado con vista de módulos',
    'description': '''
        Módulo que proporciona un panel principal visualmente atractivo
        donde los usuarios pueden ver solo los módulos a los que tienen acceso.
    ''',
    'author': 'Safinsa',
    'category': 'Tools',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard.xml',
        'views/dashboard_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_dashboard/static/src/css/dashboard.css',
            'custom_dashboard/static/src/js/dashboard.js',
            'custom_dashboard/static/src/xml/dashboard_templates.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
