# -*- coding: utf-8 -*-
# permisos/models/permiso.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.osv import expression
from logging import getLogger
_logger = getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'
    

    # 1er. Primer nivel: verificar si tiene el permiso
    def has_perm(self, modulo_code, permiso_code, empresa_id=None, sucursal_id=None, bodega_id=None):
        """
            Evalúa si el usuario tiene el permiso, considerando:
            1) Admin por accesos (accesos.acceso.is_admin)
            2) Rangos asignados (global/empresa/sucursal)
            3) Overrides puntuales (deny gana sobre allow)

            Parámetros:
                modulo_code (str): Código del módulo funcional. Ej.: 'ventas', 'inventario'.
                permiso_code (str): Código del permiso atómico dentro del módulo. Ej.: 'editar_venta'.
                empresa_id (int|None): ID de empresas.empresa; opcional. Ej.: 3
                sucursal_id (int|None): ID de sucursales.sucursal; opcional. Ej.: 12
                bodega_id (int|None): ID de bodega (si aplica en accesos.acceso); opcional.

            Ejemplo:
                self.env.user.has_perm('ventas', 'facturar_venta', empresa_id=1, sucursal_id=5)
                -> True / False
        """
        res = {}
        Permiso = self.env['permisos.permiso'].sudo()
        AsigRango = self.env['permisos.asignacion.rango'].sudo()
        AsigPerm = self.env['permisos.asignacion.permiso'].sudo()
        Acceso = self.env['accesos.acceso'].sudo()

        for user in self:
            # === 0) Resolver permiso objetivo de una vez
            target_perm = Permiso.search([
                ('active', '=', True),
                ('code', '=', permiso_code),
                ('modulo_id.code', '=', modulo_code),
            ], limit=1)

            if not target_perm:
                _logger.info("PERM: no existe permiso %s/%s", modulo_code, permiso_code)
                res[user.id] = False
                continue
            scope = target_perm.scope 

            # 1) Admin por accesos (global/empresa/sucursal/bodega según existan campos)
            dom_admin_parts = [[('usuario_id', '=', user.id)]]
            if scope in ('empresa', 'empresa_sucursal', 'empresa_sucursal_bodega') and empresa_id is not None:
                dom_admin_parts.append(['|', ('empresa_id', '=', False), ('empresa_id', '=', empresa_id)])
            # sucursal si tu modelo accesos.acceso la tiene
            if scope in ('empresa_sucursal', 'empresa_sucursal_bodega') and 'sucursal_id' in Acceso._fields and sucursal_id is not None:
                dom_admin_parts.append(['|', ('sucursal_id', '=', False), ('sucursal_id', '=', sucursal_id)])
            # bodega si la maneja accesos.acceso
            if scope == 'empresa_sucursal_bodega' and 'bodega_id' in Acceso._fields and bodega_id is not None:
                dom_admin_parts.append(['|', ('bodega_id', '=', False), ('bodega_id', '=', bodega_id)])

            dom_admin = expression.AND(dom_admin_parts)
            admin = Acceso.search(dom_admin, limit=1)
            if admin and getattr(admin, 'is_admin', False):
                _logger.info("PERM[%s]: ADMIN ok por accesos -> True", user.id)
                res[user.id] = True
                continue

            # 2) Rangos aplicables (solo añadimos filtros de las dimensiones que aplique el scope y que vengan definidas)
            base = [('usuario_id', '=', user.id), ('active', '=', True)]
            parts = [base]
            if scope in ('empresa', 'empresa_sucursal', 'empresa_sucursal_bodega') and empresa_id is not None:
                parts.append(['|', ('empresa_id', '=', False), ('empresa_id', '=', empresa_id)])
            if scope in ('empresa_sucursal', 'empresa_sucursal_bodega') and sucursal_id is not None:
                parts.append(['|', ('sucursal_id', '=', False), ('sucursal_id', '=', sucursal_id)])
            if scope == 'empresa_sucursal_bodega' and bodega_id is not None and 'bodega_id' in AsigRango._fields:
                parts.append(['|', ('bodega_id', '=', False), ('bodega_id', '=', bodega_id)])

            dom_r = expression.AND(parts)
            rango_asigs = AsigRango.search(dom_r)
            rango_perm = rango_asigs.mapped('rango_id.permiso_ids').filtered(lambda p: p.active) if rango_asigs else Permiso.browse()
            has = target_perm in rango_perm

            # 3) Overrides (mismo criterio de filtros)
            base_o = [('usuario_id', '=', user.id), ('permiso_id', '=', target_perm.id), ('active', '=', True)]
            parts_o = [base_o]
            if scope in ('empresa', 'empresa_sucursal', 'empresa_sucursal_bodega') and empresa_id is not None:
                parts_o.append(['|', ('empresa_id', '=', False), ('empresa_id', '=', empresa_id)])
            if scope in ('empresa_sucursal', 'empresa_sucursal_bodega') and sucursal_id is not None:
                parts_o.append(['|', ('sucursal_id', '=', False), ('sucursal_id', '=', sucursal_id)])
            if scope == 'empresa_sucursal_bodega' and bodega_id is not None and 'bodega_id' in AsigPerm._fields:
                parts_o.append(['|', ('bodega_id', '=', False), ('bodega_id', '=', bodega_id)])

            dom_o = expression.AND(parts_o)
            overrides = AsigPerm.search(dom_o)
            if overrides:
                if any(not o.allow for o in overrides):
                    has = False
                elif any(o.allow for o in overrides):
                    has = True

            _logger.info("PERM[%s]: rango=%s overrides=%s -> has=%s",
                         user.id, bool(rango_asigs), [(o.id, o.allow) for o in overrides], has)
            res[user.id] = bool(has)

        return res[self.id] if len(self) == 1 else res

    def check_perm(self, modulo_code, permiso_code, empresa_id=None, sucursal_id=None, bodega_id=None):
        """
            Valida que el usuario tenga el permiso; si no, lanza ValidationError.

            Parámetros:
                modulo_code (str): Código del módulo. Ej.: 'ventas'
                permiso_code (str): Código del permiso. Ej.: 'confirmar_venta'
                empresa_id (int|None): ID de empresa; opcional.
                sucursal_id (int|None): ID de sucursal; opcional.
                bodega_id (int|None): ID de bodega (si aplica).

            Ejemplo:
                self.env.user.check_perm('ventas', 'editar_venta', empresa_id=1)
                # -> True (si tiene) / lanza ValidationError (si no)
        """
        for user in self:
            ok = user.has_perm(modulo_code, permiso_code, empresa_id=empresa_id, sucursal_id=sucursal_id, bodega_id=bodega_id)
            if not ok:
                raise ValidationError(_(
                    "No cuentas con el permiso requerido: %(mod)s / %(perm)s",
                    mod=modulo_code, perm=permiso_code
                ))
        return True


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

    _sql_constraints = [
        ('permisos_modulo_code_uniq', 'unique(code)', 'El código de módulo debe ser único.')
    ]

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