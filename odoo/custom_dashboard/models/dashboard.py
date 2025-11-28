# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)
# Prefijos de xmlid que indican que un menú es de Odoo (core)
ODOO_MENU_PREFIXES = (
    'base.',
    'mail.',
    'web.',
    'contacts.',
    'auth_',
    'portal.',
    'bus.',
    'digest.',
    'fetchmail.',
    'iap.',
    'sms.',
    'snailmail.',
    'phone_validation.',
    'resource.',
    'uom.',
    'product.',  # Si no usas productos propios
    'stock.',    # Si no usas inventario propio
    'sale.',     # Si no usas ventas propias
    'purchase.', # Si no usas compras propias
    'account.',  # Si no usas contabilidad propia
    'hr.',       # Si no usas RRHH propio
    'crm.',      # Si no usas CRM propio
)

# Modelos de Odoo que NO queremos mostrar
ODOO_MODELS_BLACKLIST = {
    'res.users',
    'res.groups',
    'res.company',
    'res.partner',
    'res.config.settings',
    'ir.ui.menu',
    'ir.model',
    'ir.model.fields',
    'ir.actions.act_window',
    'ir.rule',
    'ir.module.module',
    'mail.channel',
    'mail.message',
    'mail.activity',
}

class DashboardModule(models.Model):
    _name = 'dashboard.module'
    _description = 'Dashboard Module Configuration'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre del Módulo', required=True)
    technical_name = fields.Char(string='Nombre Técnico', required=True)
    icon = fields.Char(string='Icono FontAwesome', default='fa-cube')
    color = fields.Char(string='Color (clase CSS)', default='bg-blue-500')
    description = fields.Text(string='Descripción')
    category = fields.Selection([
        ('ventas', 'Ventas'),
        ('contabilidad', 'Contabilidad'),
        ('inventario', 'Inventario'),
        ('rrhh', 'Recursos Humanos'),
        ('productividad', 'Productividad'),
        ('marketing', 'Marketing'),
        ('otros', 'Otros'),
    ], string='Categoría', default='otros')
    menu_id = fields.Many2one('ir.ui.menu', string='Menú Relacionado')
    action_id = fields.Many2one('ir.actions.act_window', string='Acción')
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)
    group_ids = fields.Many2many('res.groups', string='Grupos con Acceso')

    @api.model
    def get_user_modules(self):
        """Obtiene los módulos a los que el usuario actual tiene acceso"""
        user = self.env.user
        
        # Obtener todos los módulos activos
        all_modules = self.search([('active', '=', True)])
        
        accessible_modules = []
        for module in all_modules:
                        # Si no tiene grupos definidos, es accesible para todos
            if not module.group_ids:
                accessible_modules.append(module)
            # Si tiene grupos, verificar si el usuario pertenece a alguno
            elif module.group_ids & user.groups_id:
                accessible_modules.append(module)

        return [{
            'id': mod.id,
            'name': mod.name,
            'technical_name': mod.technical_name,
            'icon': mod.icon,
            'color': mod.color,
            'description': mod.description or '',
            'category': mod.category,
            'menu_id': mod.menu_id.id if mod.menu_id else False,
            'action_id': mod.action_id.id if mod.action_id else False,
        } for mod in accessible_modules]

    @api.model
    def get_installed_apps(self):
        """Obtiene las aplicaciones instaladas como módulos del dashboard"""
        user = self.env.user
        
        # Obtener menús raíz (aplicaciones principales)
        Menu = self.env['ir.ui.menu']
        root_menus = Menu.search([
            ('parent_id', '=', False),
        ])
        
        # Colores predefinidos para las categorías
        colors = {
            'Sales': 'bg-purple-500',
            'CRM': 'bg-blue-500',
            'Invoicing': 'bg-green-500',
            'Accounting': 'bg-emerald-600',
            'Inventory': 'bg-amber-500',
            'Purchase': 'bg-cyan-600',
            'Manufacturing': 'bg-slate-600',
            'Employees': 'bg-indigo-500',
            'Payroll': 'bg-teal-500',
            'Time Off': 'bg-pink-500',
            'Recruitment': 'bg-violet-500',
            'Project': 'bg-rose-500',
            'Calendar': 'bg-sky-500',
            'Documents': 'bg-yellow-500',
            'Website': 'bg-lime-500',
            'Email Marketing': 'bg-fuchsia-500',
            'Point of Sale': 'bg-orange-500',
            'Expenses': 'bg-red-500',
        }
        
        # Iconos predefinidos
        icons = {
            'Sales': 'fa-shopping-cart',
            'CRM': 'fa-handshake',
            'Invoicing': 'fa-file-invoice-dollar',
            'Accounting': 'fa-calculator',
            'Inventory': 'fa-boxes',
            'Purchase': 'fa-truck-loading',
            'Manufacturing': 'fa-industry',
            'Employees': 'fa-users',
            'Payroll': 'fa-money-check-alt',
            'Time Off': 'fa-calendar-times',
            'Recruitment': 'fa-user-plus',
            'Project': 'fa-project-diagram',
            'Calendar': 'fa-calendar-alt',
            'Documents': 'fa-folder-open',
            'Website': 'fa-globe',
            'Email Marketing': 'fa-envelope-open-text',
            'Point of Sale': 'fa-cash-register',
            'Expenses': 'fa-receipt',
        }
        
        # Categorías
        categories = {
            'Sales': 'ventas',
            'CRM': 'ventas',
            'Invoicing': 'contabilidad',
            'Accounting': 'contabilidad',
            'Inventory': 'inventario',
            'Purchase': 'inventario',
            'Manufacturing': 'inventario',
            'Employees': 'rrhh',
            'Payroll': 'rrhh',
            'Time Off': 'rrhh',
            'Recruitment': 'rrhh',
            'Project': 'productividad',
            'Calendar': 'productividad',
            'Documents': 'productividad',
            'Website': 'marketing',
            'Email Marketing': 'marketing',
            'Point of Sale': 'ventas',
            'Expenses': 'contabilidad',
        }
        
        accessible_apps = []
        for menu in root_menus:
            # Si el menú tiene grupos, verificar si el usuario pertenece a alguno
            if menu.groups_id and not (menu.groups_id & user.groups_id):
                continue

            # Si no tiene acción asociada, no lo mostramos
            if not menu.action:
                continue

            accessible_apps.append({
                'id': menu.id,
                'name': menu.name,
                'technical_name': menu.complete_name,
                'icon': icons.get(menu.name, 'fa-cube'),
                'color': colors.get(menu.name, 'bg-gray-500'),
                'description': f'Acceder al módulo de {menu.name}',
                'category': categories.get(menu.name, 'otros'),
                'menu_id': menu.id,
                'action_id': menu.action.id if menu.action else False,
            })

        
        return accessible_apps
    
    @api.model
    def get_dashboard_modules(self):
        """
        Devuelve las tarjetas que verá el usuario en el Panel Principal.
        SOLO módulos con acceso en accesos.acceso + show_in_dashboard=True.
        """
        user = self.env.user
        Acceso = self.env['accesos.acceso'].sudo()
        Menu = self.env['ir.ui.menu'].sudo()

        modules = []
        seen_menu_ids = set()

        # 1) Panel Principal siempre visible (si existe el menú)
        panel_menu = Menu.search([
            ('name', '=', 'Panel Principal'),
            ('parent_id', '=', False),
        ], limit=1)
        if panel_menu and panel_menu.action:
            modules.append(self._build_menu_payload(
                panel_menu,
                default_icon='fa-home',
                default_color='bg-purple-500',
                default_category='otros',
                default_desc='Acceder al Panel Principal',
            ))
            seen_menu_ids.add(panel_menu.id)

        # 2) Accesos configurados para el usuario
        accesos = Acceso.search([
            ('usuario_id', '=', user.id),
            ('active', '=', True),
        ])

        _logger.info(
            "DASHBOARD: usuario=%s accesos=%s",
            user.id,
            [(a.modulo_id.code, a.modulo_id.show_in_dashboard, a.modulo_id.menu_ids.ids) for a in accesos],
        )

        for acceso in accesos:
            modulo = acceso.modulo_id

            _logger.info(
                "DASHBOARD: evaluando modulo code=%s name=%s show_in_dashboard=%s menu_ids=%s",
                modulo.code,
                modulo.name,
                modulo.show_in_dashboard,
                modulo.menu_ids.ids,
            )

            # Solo módulos marcados para mostrarse en el panel
            if not modulo.show_in_dashboard:
                _logger.info(
                    "DASHBOARD: SKIP modulo %s -> show_in_dashboard=False",
                    modulo.code,
                )
                continue

            # Elegir UN menú para la tarjeta
            menu = self._select_dashboard_menu(modulo)
            if not menu:
                _logger.info(
                    "DASHBOARD: SKIP modulo %s -> _select_dashboard_menu devolvió vacío",
                    modulo.code,
                )
                continue

            if menu.id in seen_menu_ids:
                _logger.info(
                    "DASHBOARD: SKIP menu id=%s name=%s -> ya estaba en seen_menu_ids",
                    menu.id,
                    menu.name,
                )
                continue

            _logger.info(
                "DASHBOARD: ADD card para menu id=%s name=%s modulo=%s",
                menu.id,
                menu.name,
                modulo.code,
            )
            modules.append(self._build_menu_payload(menu))
            seen_menu_ids.add(menu.id)

        _logger.info(
            "DASHBOARD: modules resultantes para user=%s -> %s",
            user.id,
            [(m['name'], m['menu_id'], m['category']) for m in modules],
        )
        return modules
    
    def _is_odoo_menu(self, menu):
        """
        Determina si un menú es de Odoo (core) basándose en:
        1. Su xmlid (external_id)
        2. El modelo de su acción
        """
        if not menu:
            return True

        # 1) Verificar por xmlid
        external_ids = menu.get_external_id()
        xmlid = external_ids.get(menu.id, '')
        if xmlid:
            for prefix in ODOO_MENU_PREFIXES:
                if xmlid.startswith(prefix):
                    _logger.debug(
                        "[_is_odoo_menu] Menu %s (xmlid=%s) es de Odoo por prefix",
                        menu.name, xmlid
                    )
                    return True

        # 2) Verificar por modelo de la acción
        if menu.action and hasattr(menu.action, 'res_model'):
            model = menu.action.res_model
            if model in ODOO_MODELS_BLACKLIST:
                _logger.debug(
                    "[_is_odoo_menu] Menu %s apunta a modelo Odoo: %s",
                    menu.name, model
                )
                return True

        return False


    def _build_menu_payload(self, menu,
                            default_icon='fa-cube',
                            default_color='bg-gray-500',
                            default_category='otros',
                            default_desc=None):
        dash = self.search([('menu_id', '=', menu.id)], limit=1)

        name = dash.name or menu.name if dash else menu.name
        technical_name = dash.technical_name or menu.complete_name if dash else menu.complete_name
        icon = dash.icon or default_icon if dash else default_icon
        color = dash.color or default_color if dash else default_color
        category = dash.category or default_category if dash else default_category
        description = (
            dash.description
            or default_desc
            or f'Acceder al módulo de {menu.name}'
        ) if dash else (default_desc or f'Acceder al módulo de {menu.name}')

        # Priorizamos la acción configurada en dashboard.module
        action = (dash.action_id if dash and dash.action_id else menu.action)

        return {
            'id': menu.id,
            'name': name,
            'technical_name': technical_name,
            'icon': icon,
            'color': color,
            'description': description,
            'category': category,
            'menu_id': menu.id,
            'action_id': action.id if action else False,
        }
    
    @api.model
    def _select_dashboard_menu(self, modulo, exclude_odoo=True):
        """
        Recibe un record de `permisos.modulo` y devuelve UN ir.ui.menu
        para representarlo en el dashboard.

        PRIORIDADES:
        1) Si custom_menu_id está definido, usarlo (nuevo campo)
        2) Si dashboard_menu_id está definido, usarlo
        3) Si hay dashboard.module con menu_id, usarlo
        4) Buscar menú raíz (sin parent) con acción que NO sea de Odoo
        5) Buscar cualquier menú con acción que NO sea de Odoo
        6) Si exclude_odoo=True y todos son de Odoo -> devolver vacío (NO fallback)
        """
        Menu = self.env['ir.ui.menu'].sudo()
        Dash = self.env['dashboard.module'].sudo()

        if not modulo:
            return Menu.browse()

        menus = modulo.menu_ids
        if not menus:
            _logger.warning(
                "[%s] _select_dashboard_menu: módulo sin menús ligados",
                modulo.code
            )
            return Menu.browse()

        # 1) custom_menu_id explícito (nuevo campo para menú propio)
        if hasattr(modulo, 'custom_menu_id') and modulo.custom_menu_id:
            if not exclude_odoo or not self._is_odoo_menu(modulo.custom_menu_id):
                _logger.info(
                    "[%s] usando custom_menu_id: %s",
                    modulo.code, modulo.custom_menu_id.name
                )
                return modulo.custom_menu_id

        # 2) dashboard_menu_id explícito
        if hasattr(modulo, 'dashboard_menu_id') and modulo.dashboard_menu_id:
            if not exclude_odoo or not self._is_odoo_menu(modulo.dashboard_menu_id):
                _logger.info(
                    "[%s] usando dashboard_menu_id: %s",
                    modulo.code, modulo.dashboard_menu_id.name
                )
                return modulo.dashboard_menu_id

        # 3) Config explícita en dashboard.module
        dash_rec = Dash.search([
            ('menu_id', 'in', menus.ids),
            ('active', '=', True),
        ], limit=1)
        if dash_rec and dash_rec.menu_id:
            if not exclude_odoo or not self._is_odoo_menu(dash_rec.menu_id):
                _logger.info(
                    "[%s] usando dashboard.module: %s",
                    modulo.code, dash_rec.menu_id.name
                )
                return dash_rec.menu_id

        # 4) Filtrar menús de Odoo
        if exclude_odoo:
            valid_menus = Menu.browse()
            for menu in menus:
                if not self._is_odoo_menu(menu):
                    valid_menus |= menu
                else:
                    _logger.info(
                        "[%s] excluyendo menú de Odoo: %s",
                        modulo.code, menu.name
                    )

            if not valid_menus:
                _logger.warning(
                    "[%s] TODOS los menús son de Odoo, NO se mostrará en dashboard",
                    modulo.code
                )
                # NO hacemos fallback -> devolvemos vacío
                return Menu.browse()
        else:
            valid_menus = menus

        # 5) Menú raíz con acción
        root_with_action = valid_menus.filtered(lambda m: not m.parent_id and m.action)
        if root_with_action:
            _logger.info(
                "[%s] usando menú raíz con acción: %s",
                modulo.code, root_with_action[0].name
            )
            return root_with_action[0]

        # 6) Cualquier menú con acción
        with_action = valid_menus.filtered('action')
        if with_action:
            _logger.info(
                "[%s] usando primer menú con acción: %s",
                modulo.code, with_action[0].name
            )
            return with_action[0]

        # 7) El primero disponible (solo si hay válidos)
        if valid_menus:
            _logger.info(
                "[%s] usando primer menú disponible: %s",
                modulo.code, valid_menus[0].name
            )
            return valid_menus[0]

        return Menu.browse()



class DashboardFavorite(models.Model):
    _name = 'dashboard.favorite'
    _description = 'User Dashboard Favorites'

    user_id = fields.Many2one('res.users', string='Usuario', required=True, 
                              default=lambda self: self.env.user, ondelete='cascade')
    module_id = fields.Many2one('dashboard.module', string='Módulo', ondelete='cascade')
    menu_id = fields.Many2one('ir.ui.menu', string='Menú', ondelete='cascade')

    _sql_constraints = [
        ('unique_user_module', 'unique(user_id, module_id)', 
         'El módulo ya está en favoritos'),
        ('unique_user_menu', 'unique(user_id, menu_id)', 
         'El menú ya está en favoritos'),
    ]

    @api.model
    def toggle_favorite(self, menu_id):
        """Agrega o elimina un favorito"""
        existing = self.search([
            ('user_id', '=', self.env.uid),
            ('menu_id', '=', menu_id)
        ])
        if existing:
            existing.unlink()
            return False
        else:
            self.create({
                'user_id': self.env.uid,
                'menu_id': menu_id
            })
            return True

    @api.model
    def get_favorites(self):
        """Obtiene los IDs de los favoritos del usuario"""
        favorites = self.search([('user_id', '=', self.env.uid)])
        return [fav.menu_id.id for fav in favorites if fav.menu_id]
