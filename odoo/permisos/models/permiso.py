# -*- coding: utf-8 -*-
# permisos/models/permiso.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.osv import expression
from logging import getLogger
_logger = getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'
    

    def action_open_permisos_wizard(self):
        self.ensure_one()
        # Abre el wizard correcto (efectivo), que sí tiene usuario_id
        wiz = self.env['permisos.efectivo.wiz'].create({'usuario_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Permisos del Usuario'),
            'res_model': 'permisos.efectivo.wiz',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wiz.id,
        }
    
    def _resolve_ctx_from_user_module(self, modulo_code, empresa_id, sucursal_id, bodega_id):
        empresa_id = getattr(empresa_id, 'id', empresa_id) or False
        sucursal_id = getattr(sucursal_id, 'id', sucursal_id) or False
        bodega_id  = getattr(bodega_id,  'id', bodega_id)  or False
        if empresa_id and (sucursal_id or bodega_id):
            return empresa_id, sucursal_id, bodega_id
        # buscar contexto por módulo
        Ctx = self.env['permisos.user.context'].sudo()
        mod = self.env['permisos.modulo'].sudo().search([('code','=', modulo_code)], limit=1)
        if mod:
            ctx = Ctx.search([('usuario_id','=', self.id), ('modulo_id','=', mod.id)], limit=1)
            if ctx:
                empresa_id  = empresa_id  or (ctx.empresa_id.id  or False)
                sucursal_id = sucursal_id or (ctx.sucursal_id.id or False)
                bodega_id   = bodega_id   or (ctx.bodega_id.id   or False)
        return empresa_id, sucursal_id, bodega_id



#Se guardan los permisos de modulo funcionales
#No autoriza nada por sí mismo; sirve para organizar y para que has_perm() sepa en qué área buscar. Agrupador/área
class PermModulo(models.Model):
    _name = 'permisos.modulo'
    _description = 'Módulo funcional para agrupar permisos'
    _order = 'code'
    code = fields.Char('Código', required=True, index=True, help=_("Clave técnica única del módulo (área funcional).\n"
               "Formato sugerido: minúsculas, sin espacios.\n"
               "Ejemplos: 'ventas', 'inventario', 'facturas'."))
    name = fields.Char('Nombre', required=True ,help=_("Nombre legible del módulo.\n" "Ejemplo: 'Ventas'."))
    description = fields.Text('Descripción', help=_("Describe brevemente el alcance del módulo.\n" "Ejemplo: 'Operaciones y flujo de ventas (cotización, pedido, factura)'."))
    active = fields.Boolean(default=True)
    group_id = fields.Many2one('res.groups', string='Grupo del módulo')

    # NUEVO: grupos por nivel
    group_read_id   = fields.Many2one('res.groups', string='[R] Lectura')
    group_write_id  = fields.Many2one('res.groups', string='[RW] Edición')
    group_create_id = fields.Many2one('res.groups', string='[RWC] Creación')
    group_admin_id  = fields.Many2one('res.groups', string='[ADMIN] Todo')

    menu_ids = fields.Many2many(
        'ir.ui.menu', 'permisos_modulo_menu_rel', 'modulo_id', 'menu_id',
        string='Menús del módulo'
    )
    dirty = fields.Boolean(string='Pendiente aplicar', default=False)

    _sql_constraints = [
        ('permisos_modulo_code_uniq', 'unique(code)', 'El código de módulo debe ser único.')
    ]

    @api.onchange('name', 'description', 'active')
    def _onchange_mark_dirty(self):
        for r in self:
            r.dirty = True

    @api.onchange('menu_ids')
    def _onchange_menus_mark_dirty(self):
        for r in self:
            r.dirty = True

    # --- NORMALIZA el code siempre a minúsculas/trim ---
    @api.model
    def create(self, vals):
        if 'code' in vals:
            vals['code'] = (vals.get('code') or '').strip().lower()
        rec = super().create(vals)
        # marca dirty para que el botón "Aplicar seguridad" aparezca
        rec.dirty = True
        return rec

    def write(self, vals):
        vals = vals.copy()
        if 'code' in vals:
            vals['code'] = (vals.get('code') or '').strip().lower()
        # si cambian campos relevantes, marcar dirty en el MISMO write
        if {'code', 'name', 'description', 'active', 'menu_ids'} & set(vals.keys()):
            vals['dirty'] = True
        res = super().write(vals)
        # si cambian code/name, renombrar el grupo coherente "[code] name"
        if {'code', 'name'} & set(vals.keys()):
            for r in self.filtered('group_id'):
                r.group_id.sudo().write({'name': f"[{r.code}] {r.name}"})
        return res

    # --- BLOQUEA BORRADO con mensaje agregando conteos de dependencias ---
    def unlink(self):
        Perm = self.env['permisos.permiso'].sudo()
        Acc  = self.env['accesos.acceso'].sudo()
        Ctx  = self.env['permisos.user.context'].sudo()
        Conf = self.env['permisos.modulo.model'].sudo()

        for mod in self:
            blocks = {
                'permisos':       Perm.search_count([('modulo_id', '=', mod.id)]),
                'accesos':        Acc.search_count([('modulo_id', '=', mod.id), ('active', '=', True)]),
                'contextos':      Ctx.search_count([('modulo_id', '=', mod.id)]),
                'config_modelos': Conf.search_count([('modulo_id', '=', mod.id)]),
            }
            if any(blocks.values()):
                det = []
                if blocks['permisos']:
                    det.append(_("- %(n)s permisos del módulo", n=blocks['permisos']))
                if blocks['accesos']:
                    det.append(_("- %(n)s accesos de usuarios (accesos.acceso) activos", n=blocks['accesos']))
                if blocks['contextos']:
                    det.append(_("- %(n)s contextos de usuario", n=blocks['contextos']))
                if blocks['config_modelos']:
                    det.append(_("- %(n)s configuraciones de modelos (permisos.modulo.model)", n=blocks['config_modelos']))

                raise ValidationError(_(
                    "No se puede eliminar el módulo “%(mod)s” porque tiene registros relacionados:\n"
                    "%(det)s\n\n"
                    "Sugerencias:\n"
                    "• Archiva el módulo (active=False) en lugar de eliminarlo.\n"
                    "• O elimina primero los registros relacionados (Permisos, Accesos, Contextos, Config. de modelos)."
                ) % {'mod': mod.display_name, 'det': "\n".join(det)})

        return super().unlink()



#Se guardan los permisos atómicos
#Acción puntual que se concede/deniega y es lo que consulta has_perm/check_perm.
class PermPermiso(models.Model):
    _name = 'permisos.permiso'
    _description = 'Permiso atómico dentro de un módulo'
    _order = 'modulo_id, code'

    code = fields.Char('Código', required=True, index=True, help=_("Clave técnica del permiso (acción atómica) dentro del módulo.\n"
        "Formato: alfanumérico y guión bajo.\n"
        "Ejemplos: 'crear_venta', 'editar_venta', 'facturar_venta'."))  # p.ej.: crear_venta
    name = fields.Char('Nombre', required=True , help=_("Nombre visible del permiso.\n" "Ejemplo: 'Editar venta'.")
                        )# p.ej.: Crear venta
    modulo_id = fields.Many2one('permisos.modulo', string='Módulo', required=True, ondelete='restrict', index=True,
                                help=_("Módulo (área) al que pertenece el permiso.\n" "Ejemplo: seleccione el módulo 'ventas' para 'editar_venta'.")
                                )
    description = fields.Text('Descripción' , help=_("Detalle adicional del permiso.\n"
               "Ejemplo: 'Permite modificar líneas y totales de una venta antes de confirmar'.")
               )
    active = fields.Boolean(default=True)
    #Decide qué dimensiones filtrar
    scope = fields.Selection(
        selection=[
            ('global', 'Global (sin contexto)'),
            ('empresa', 'Por empresa'),
            ('empresa_sucursal', 'Por empresa + sucursal'),
            ('empresa_sucursal_bodega', 'Por empresa + sucursal + bodega'),
        ],
        required=True, default='empresa',
        string='Ámbito'
    )

    _sql_constraints = [
        ('permisos_permiso_mod_code_uniq', 'unique(modulo_id, code)',
         'El código de permiso debe ser único dentro del módulo.')
    ]

    @api.constrains('code')
    def _check_code_format(self):
        for r in self:
            if not r.code or not r.code.replace('_', '').isalnum():
                raise ValidationError(_('El código del permiso debe ser alfanumérico con guiones bajos.'))
#Se guardan los rangos (paquetes de permisos). Estructura.
class PermRango(models.Model):
    _name = 'permisos.rango'
    _description = 'Rango (paquete de permisos)'
    _order = 'code'

    code = fields.Char('Código', required=True, index=True, help=_("Clave técnica del rango/rol.\n"
               "Ejemplos: 'capturista_venta', 'supervisor_venta'."))   # p.ej.: capturista_venta
    name = fields.Char('Nombre', required=True, help=_("Nombre visible del rango.\n"
               "Ejemplo: 'Supervisor de venta'."))
    description = fields.Text('Descripción', help=_("Describe el alcance del rango.\n"
               "Ejemplo: 'Puede crear/editar/enviar a comité; no confirma ni factura'."))
    permiso_ids = fields.Many2many('permisos.permiso', 'permisos_rango_permiso_rel',
                                   'rango_id', 'permiso_id', string='Permisos',
                                   help=_("Permisos atómicos que incluye este rango.\n" "Ejemplo: agregar 'ventas/crear_venta', 'ventas/editar_venta', 'ventas/enviar_comite'.")
                                   )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('permisos_rango_code_uniq', 'unique(code)', 'El código del rango debe ser único.')
    ]

# Asignaciones de rangos a usuarios con contexto
# Da la base de permisos del usuario (suma todo lo que traen sus rangos aplicables al contexto).
class PermAsignacionRango(models.Model):
    _name = 'permisos.asignacion.rango'
    _description = 'Asignación de rango(s) a usuario con contexto'
    _order = 'id desc'
    _check_company_auto = False

    usuario_id = fields.Many2one('res.users', string='Usuario', required=True, ondelete='cascade', index=True,
                                 help=_("Usuario al que se asigna el rango.\n" "Ejemplo: 'Juan Pérez'.")
                                 )
    rango_id = fields.Many2one('permisos.rango', string='Rango', required=True, ondelete='restrict', index=True,
                               help=_("Rango/rol a asignar (paquete de permisos).\n" "Ejemplo: 'capturista_venta'.")
                               )
    empresa_id = fields.Many2one('empresas.empresa', string='Empresa', ondelete='restrict', index=True,
                                 help=_("Opcional. Si lo estableces, el rango aplica solo en esa empresa.\n"
                                    "Si lo dejas vacío, aplica de forma global.\n"
                                    "Ejemplo: Empresa = 'Matriz'.")
                                 )
    sucursal_id = fields.Many2one('sucursales.sucursal', string='Sucursal', ondelete='restrict', index=True,
                                  help=_("Opcional. Si lo estableces, el rango aplica solo en esa sucursal (que pertenezca a la empresa indicada).\n"
                                    "Ejemplo: Sucursal = 'Sucursal Centro'.")
                                  )
    bodega_id = fields.Many2one('bodegas.bodega', string='Bodega', ondelete='restrict', index=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('permisos_asig_rango_unique',
         'unique(usuario_id, rango_id, empresa_id, sucursal_id, bodega_id)',
         'Ya existe esa asignación de rango para ese usuario y contexto.'),
    ]


    @api.constrains('sucursal_id', 'empresa_id', 'bodega_id')
    def _check_contexto_vs_empresa(self):
        for r in self:
            if r.sucursal_id and r.empresa_id and r.sucursal_id.empresa.id != r.empresa_id.id:
                raise ValidationError(_('La sucursal no pertenece a la empresa.'))
            if r.bodega_id and r.empresa_id and r.bodega_id.empresa_id.id != r.empresa_id.id:
                raise ValidationError(_('La bodega no pertenece a la empresa.'))

# Asignaciones de overrides de permisos a usuarios con contexto
#Ajusta la base solo para ese permiso: permite o deniega explícitamente. hace una excepcion a lo que traen los rangos.
class PermAsignacionPermiso(models.Model):
    _name = 'permisos.asignacion.permiso'
    _description = 'Override de permiso por usuario (permitir o denegar)'
    _order = 'id desc'
    _check_company_auto = False

    usuario_id = fields.Many2one('res.users', string='Usuario', required=True, ondelete='cascade', index=True, 
                                 help=_("Usuario al que se aplica la excepción.\n"
                                    "Ejemplo: 'María López'.")
                                 )
    permiso_id = fields.Many2one('permisos.permiso', string='Permiso', required=True, ondelete='restrict', index=True,
                                 help=_("Permiso atómico a forzar en este usuario.\n"
                                 "Ejemplo: 'ventas/facturar_venta'.")
                                 )
    allow = fields.Boolean('Permitir', default=True, help=_("Define el tipo de excepción:\n"
                            "• Marcado (True) = PERMITIR aunque el rango no lo tenga.\n"
                            "• Desmarcado (False) = DENEGAR aunque el rango lo tenga.\n"
                            "Ejemplo: desmarcar para bloquear 'ventas/editar_venta'."))
    empresa_id = fields.Many2one('empresas.empresa', string='Empresa', ondelete='restrict', index=True,
                                 help=_("Opcional. Si lo estableces, la excepción aplica solo en esa empresa.\n"
                                    "Si lo dejas vacío, aplica globalmente.\n"
                                    "Ejemplo: Empresa = 'Matriz'.")
                                 )
    sucursal_id = fields.Many2one('sucursales.sucursal', string='Sucursal', ondelete='restrict', index=True,
                                  help=_("Opcional. Si lo estableces, la excepción aplica solo en esa sucursal.\n"
                                    "Ejemplo: Sucursal = 'Sucursal Norte'.")
                                  )
    bodega_id = fields.Many2one('bodegas.bodega', string='Bodega', ondelete='restrict', index=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('permisos_asig_perm_unique',
         'unique(usuario_id, permiso_id, empresa_id, sucursal_id, bodega_id)',
         'Ya existe un override para ese permiso/usuario en ese contexto.'),
    ]


    @api.constrains('sucursal_id', 'empresa_id', 'bodega_id')
    def _check_contexto_vs_empresa(self):
        for r in self:
            if r.sucursal_id and r.empresa_id and r.sucursal_id.empresa.id != r.empresa_id.id:
                raise ValidationError(_('La sucursal no pertenece a la empresa.'))
            if r.bodega_id and r.empresa_id and r.bodega_id.empresa_id.id != r.empresa_id.id:
                raise ValidationError(_('La bodega no pertenece a la empresa.'))