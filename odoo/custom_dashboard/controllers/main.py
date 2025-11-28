# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json


class DashboardController(http.Controller):

    @http.route('/custom_dashboard/get_modules', type='json', auth='user')
    def get_modules(self):
        """Endpoint para obtener los módulos del usuario"""
        DashboardModule = request.env['dashboard.module']
        
        # Primero intentar obtener módulos configurados manualmente
        modules = DashboardModule.get_user_modules()
        
        # Si no hay módulos configurados, usar las apps instaladas
        if not modules:
            modules = DashboardModule.get_installed_apps()
        
        return modules

    @http.route('/custom_dashboard/get_apps', type='json', auth='user')
    def get_apps(self):
        """Endpoint para obtener todas las aplicaciones instaladas accesibles"""
        user = request.env.user
        Menu = request.env['ir.ui.menu']
        
        # Colores y configuración
        app_config = {
            'Ventas': {'icon': 'fa-shopping-cart', 'color': 'bg-purple-500', 'category': 'ventas'},
            'Sales': {'icon': 'fa-shopping-cart', 'color': 'bg-purple-500', 'category': 'ventas'},
            'CRM': {'icon': 'fa-handshake', 'color': 'bg-blue-500', 'category': 'ventas'},
            'Facturación': {'icon': 'fa-file-invoice-dollar', 'color': 'bg-green-500', 'category': 'contabilidad'},
            'Invoicing': {'icon': 'fa-file-invoice-dollar', 'color': 'bg-green-500', 'category': 'contabilidad'},
            'Contabilidad': {'icon': 'fa-calculator', 'color': 'bg-emerald-600', 'category': 'contabilidad'},
            'Accounting': {'icon': 'fa-calculator', 'color': 'bg-emerald-600', 'category': 'contabilidad'},
            'Inventario': {'icon': 'fa-boxes', 'color': 'bg-amber-500', 'category': 'inventario'},
            'Inventory': {'icon': 'fa-boxes', 'color': 'bg-amber-500', 'category': 'inventario'},
            'Compra': {'icon': 'fa-truck-loading', 'color': 'bg-cyan-600', 'category': 'inventario'},
            'Purchase': {'icon': 'fa-truck-loading', 'color': 'bg-cyan-600', 'category': 'inventario'},
            'Fabricación': {'icon': 'fa-industry', 'color': 'bg-slate-600', 'category': 'inventario'},
            'Manufacturing': {'icon': 'fa-industry', 'color': 'bg-slate-600', 'category': 'inventario'},
            'Empleados': {'icon': 'fa-users', 'color': 'bg-indigo-500', 'category': 'rrhh'},
            'Employees': {'icon': 'fa-users', 'color': 'bg-indigo-500', 'category': 'rrhh'},
            'Nómina': {'icon': 'fa-money-check-alt', 'color': 'bg-teal-500', 'category': 'rrhh'},
            'Payroll': {'icon': 'fa-money-check-alt', 'color': 'bg-teal-500', 'category': 'rrhh'},
            'Ausencias': {'icon': 'fa-calendar-times', 'color': 'bg-pink-500', 'category': 'rrhh'},
            'Time Off': {'icon': 'fa-calendar-times', 'color': 'bg-pink-500', 'category': 'rrhh'},
            'Reclutamiento': {'icon': 'fa-user-plus', 'color': 'bg-violet-500', 'category': 'rrhh'},
            'Recruitment': {'icon': 'fa-user-plus', 'color': 'bg-violet-500', 'category': 'rrhh'},
            'Proyecto': {'icon': 'fa-project-diagram', 'color': 'bg-rose-500', 'category': 'productividad'},
            'Project': {'icon': 'fa-project-diagram', 'color': 'bg-rose-500', 'category': 'productividad'},
            'Calendario': {'icon': 'fa-calendar-alt', 'color': 'bg-sky-500', 'category': 'productividad'},
            'Calendar': {'icon': 'fa-calendar-alt', 'color': 'bg-sky-500', 'category': 'productividad'},
            'Documentos': {'icon': 'fa-folder-open', 'color': 'bg-yellow-500', 'category': 'productividad'},
            'Documents': {'icon': 'fa-folder-open', 'color': 'bg-yellow-500', 'category': 'productividad'},
            'Sitio web': {'icon': 'fa-globe', 'color': 'bg-lime-500', 'category': 'marketing'},
            'Website': {'icon': 'fa-globe', 'color': 'bg-lime-500', 'category': 'marketing'},
            'Email Marketing': {'icon': 'fa-envelope-open-text', 'color': 'bg-fuchsia-500', 'category': 'marketing'},
            'Punto de Venta': {'icon': 'fa-cash-register', 'color': 'bg-orange-500', 'category': 'ventas'},
            'Point of Sale': {'icon': 'fa-cash-register', 'color': 'bg-orange-500', 'category': 'ventas'},
            'Gastos': {'icon': 'fa-receipt', 'color': 'bg-red-500', 'category': 'contabilidad'},
            'Expenses': {'icon': 'fa-receipt', 'color': 'bg-red-500', 'category': 'contabilidad'},
            'Conversaciones': {'icon': 'fa-comments', 'color': 'bg-blue-400', 'category': 'productividad'},
            'Discuss': {'icon': 'fa-comments', 'color': 'bg-blue-400', 'category': 'productividad'},
            'Contactos': {'icon': 'fa-address-book', 'color': 'bg-indigo-400', 'category': 'otros'},
            'Contacts': {'icon': 'fa-address-book', 'color': 'bg-indigo-400', 'category': 'otros'},
            'Ajustes': {'icon': 'fa-cog', 'color': 'bg-gray-600', 'category': 'otros'},
            'Settings': {'icon': 'fa-cog', 'color': 'bg-gray-600', 'category': 'otros'},
            'Tablero': {'icon': 'fa-tachometer-alt', 'color': 'bg-purple-600', 'category': 'otros'},
            'Dashboards': {'icon': 'fa-tachometer-alt', 'color': 'bg-purple-600', 'category': 'otros'},
            'Aplicaciones': {'icon': 'fa-th', 'color': 'bg-gray-500', 'category': 'otros'},
            'Apps': {'icon': 'fa-th', 'color': 'bg-gray-500', 'category': 'otros'},
        }
        
        # Obtener menús raíz accesibles por el usuario
        all_menus = Menu.search([('parent_id', '=', False)])
        
        apps = []
        for menu in all_menus:
            config = app_config.get(menu.name, {
                'icon': 'fa-cube',
                'color': 'bg-gray-500',
                'category': 'otros'
            })
            
            apps.append({
                'id': menu.id,
                'name': menu.name,
                'icon': config['icon'],
                'color': config['color'],
                'category': config['category'],
                'description': f'Acceder a {menu.name}',
                'action_id': menu.action.id if menu.action else False,
                'menu_id': menu.id,
            })
        
        return apps

    @http.route('/custom_dashboard/toggle_favorite', type='json', auth='user')
    def toggle_favorite(self, menu_id):
        """Toggle favorito para un menú"""
        Favorite = request.env['dashboard.favorite']
        return Favorite.toggle_favorite(menu_id)

    @http.route('/custom_dashboard/get_favorites', type='json', auth='user')
    def get_favorites(self):
        """Obtener favoritos del usuario"""
        Favorite = request.env['dashboard.favorite']
        return Favorite.get_favorites()

    @http.route('/custom_dashboard/get_user_info', type='json', auth='user')
    def get_user_info(self):
        """Obtener información del usuario actual"""
        user = request.env.user
        return {
            'id': user.id,
            'name': user.name,
            'email': user.email or user.login,
            'image': f'/web/image/res.users/{user.id}/avatar_128' if user.avatar_128 else False,
        }
    