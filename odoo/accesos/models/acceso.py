# accesos/models/acceso.py
# -*- coding: utf-8 -*-
from odoo import models, api, _, fields
from odoo.exceptions import ValidationError
from functools import wraps

class Acceso(models.Model):
    _name = 'accesos.acceso'
    _description = 'Acceso de usuario por módulo/contexto'
    _order = 'id desc'
    _rec_name = 'codigo'

    codigo = fields.Char(readonly=True, default=lambda s: s.env['ir.sequence'].next_by_code('accesos.acceso') or '/')
    usuario_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    modulo_id  = fields.Many2one('permisos.modulo', required=True, ondelete='restrict', index=True)
    empresa_id = fields.Many2one('empresas.empresa', ondelete='restrict', index=True)
    sucursal_id= fields.Many2one('sucursales.sucursal', ondelete='restrict', index=True)
    bodega_id  = fields.Many2one('bodegas.bodega', ondelete='restrict', index=True)

    can_read   = fields.Boolean(default=True)
    can_write  = fields.Boolean(default=False)
    can_create = fields.Boolean(default=False)
    is_admin   = fields.Boolean(default=False)
    active     = fields.Boolean(default=True)

    _sql_constraints = [
        ('acceso_uniq', 'unique(usuario_id, modulo_id, empresa_id, sucursal_id, bodega_id)',
         'Ya existe un acceso con el mismo contexto.')
    ]

    @api.constrains('sucursal_id', 'empresa_id', 'bodega_id')
    def _check_context_vs_empresa(self):
        for r in self:
            if r.sucursal_id and r.empresa_id and r.sucursal_id.empresa.id != r.empresa_id.id:
                raise ValidationError(_('La sucursal no pertenece a la empresa.'))
            if r.bodega_id and r.empresa_id and r.bodega_id.empresa_id.id != r.empresa_id.id:
                raise ValidationError(_('La bodega no pertenece a la empresa.'))


class ResUsersPerms(models.Model):
    _inherit = 'res.users'

    @api.model
    def _perm__resolve_ctx(self, modulo_code, empresa_id=None, sucursal_id=None, bodega_id=None):
        """Resuelve IDs usando: args explícitos -> contexto por módulo -> vacío."""
        Mod = self.env['permisos.modulo'].sudo()
        Ctx = self.env['permisos.user.context'].sudo()
        modulo = Mod.search([('code','=', modulo_code)], limit=1)
        emp_id = getattr(empresa_id,'id',empresa_id) or False
        suc_id = getattr(sucursal_id,'id',sucursal_id) or False
        bod_id = getattr(bodega_id,'id',bodega_id) or False
        if modulo and not (emp_id and (suc_id or True)):
            ctx = Ctx.search([('usuario_id','=', self.env.user.id), ('modulo_id','=', modulo.id)], limit=1)
            if ctx:
                emp_id = emp_id or (ctx.empresa_id.id or False)
                suc_id = suc_id or (ctx.sucursal_id.id or False)
                bod_id = bod_id or (ctx.bodega_id.id or False)
        return emp_id, suc_id, bod_id

    # --- GATE por accesos: ¿el usuario tiene algún acceso al módulo en esa empresa?
    def _perm__has_gate(self, modulo_code, empresa_id):
        if not empresa_id:
            return False
        Acc = self.env['accesos.acceso'].sudo()
        Mod = self.env['permisos.modulo'].sudo()
        modulo = Mod.search([('code','=', modulo_code)], limit=1)
        if not modulo:
            return False
        return bool(Acc.search([('usuario_id','=', self.id),
                                ('empresa_id','=', empresa_id),
                                ('modulo_id','=', modulo.id),
                                ('active','=', True)], limit=1))

    # --- Admin por gate
    def _perm__is_admin_gate(self, modulo_code, empresa_id):
        Acc = self.env['accesos.acceso'].sudo()
        Mod = self.env['permisos.modulo'].sudo()
        modulo = Mod.search([('code','=', modulo_code)], limit=1)
        if not modulo or not empresa_id:
            return False
        a = Acc.search([('usuario_id','=', self.id),
                        ('empresa_id','=', empresa_id),
                        ('modulo_id','=', modulo.id),
                        ('active','=', True)], limit=1)
        return bool(a and a.is_admin)

    # --- Permisos atómicos (tu lógica, ajustada al gate y sin empresa_actual)
    def has_perm(self, modulo_code, permiso_code, empresa_id=None, sucursal_id=None, bodega_id=None):
        self.ensure_one()
        emp_id, suc_id, bod_id = self._perm__resolve_ctx(modulo_code, empresa_id, sucursal_id, bodega_id)
        # Gate de visibilidad (si no hay gate, no hay permiso)
        if not self._perm__has_gate(modulo_code, emp_id):
            return False
        # Admin por gate
        if self._perm__is_admin_gate(modulo_code, emp_id):
            return True

        Permiso  = self.env['permisos.permiso'].sudo()
        AsigR    = self.env['permisos.asignacion.rango'].sudo()
        AsigP    = self.env['permisos.asignacion.permiso'].sudo()
        target   = Permiso.search([('active','=',True),
                                   ('code','=', permiso_code),
                                   ('modulo_id.code','=', modulo_code)], limit=1)
        if not target:
            return False
        scope = target.scope

        # Rangos aplicables
        dom = [('usuario_id','=', self.id), ('active','=', True)]
        if scope in ('empresa','empresa_sucursal','empresa_sucursal_bodega') and emp_id:
            dom += ['|', ('empresa_id','=', False), ('empresa_id','=', emp_id)]
        if scope in ('empresa_sucursal','empresa_sucursal_bodega') and suc_id:
            dom += ['|', ('sucursal_id','=', False), ('sucursal_id','=', suc_id)]
        if scope == 'empresa_sucursal_bodega' and bod_id:
            dom += ['|', ('bodega_id','=', False), ('bodega_id','=', bod_id)]
        r_asigs = AsigR.search(dom)
        perms   = r_asigs.mapped('rango_id.permiso_ids').filtered(lambda p: p.active)
        has     = target in perms

        # Overrides
        dom_o = [('usuario_id','=', self.id), ('permiso_id','=', target.id), ('active','=', True)]
        if scope in ('empresa','empresa_sucursal','empresa_sucursal_bodega') and emp_id:
            dom_o += ['|', ('empresa_id','=', False), ('empresa_id','=', emp_id)]
        if scope in ('empresa_sucursal','empresa_sucursal_bodega') and suc_id:
            dom_o += ['|', ('sucursal_id','=', False), ('sucursal_id','=', suc_id)]
        if scope == 'empresa_sucursal_bodega' and bod_id:
            dom_o += ['|', ('bodega_id','=', False), ('bodega_id','=', bod_id)]
        ovs = self.env['permisos.asignacion.permiso'].sudo().search(dom_o)
        if any(not o.allow for o in ovs):
            has = False
        elif any(o.allow for o in ovs):
            has = True
        return bool(has)

    def check_perm(self, modulo_code, permiso_code, **ctx):
        ok = self.has_perm(modulo_code, permiso_code, **ctx)
        if not ok:
            raise ValidationError(_("No cuentas con el permiso requerido: %s / %s") % (modulo_code, permiso_code))
        return True


    # Decorador
    def require_perm(modulo_code, permiso_code):
        def _wrap(method):
            @wraps(method)
            def _inner(self, *args, **kwargs):
                self.env.user.check_perm(modulo_code, permiso_code)
                return method(self, *args, **kwargs)
            return _inner
        return _wrap


# Mixin para CRUD por modelo (usa modulo_code a definir en la clase hija)
class PermittedModelMixin(models.AbstractModel):
    _name = 'permisos.permitted.mixin'
    _description = 'Mixin de validación CRUD por modelo/módulo'

    # Debe declararse en el modelo concreto, ej. modulo_code = 'ciclos'
    modulo_code = None

    def _modulo_code(self):
        return getattr(self, 'modulo_code', None)

    # Resuelve allow/deny para acción CRUD dada la config + overrides
    def _check_model_crud(self, operation):
        # operation in {'read','write','create','unlink'}
        modulo_code = self._modulo_code()
        if not modulo_code:
            return
        user = self.env.user
        Mod = self.env['permisos.modulo'].sudo().search([('code','=', modulo_code)], limit=1)
        if not Mod:
            raise ValidationError(_("Módulo no configurado: %s") % modulo_code)

        # Gate: necesita al menos un acceso en alguna empresa
        # (si el modelo tiene empresa_field en config, debería tomar el contexto; si no, con que tenga algún acceso ya ve)
        # Para CRUD fuerte, si no hay gate en ninguna empresa no permitimos.
        any_gate = self.env['accesos.acceso'].sudo().search_count([
            ('usuario_id','=', user.id), ('modulo_id','=', Mod.id), ('active','=', True)
        ]) > 0
        if not any_gate:
            raise ValidationError(_("No tienes acceso al módulo '%s' en ninguna empresa.") % modulo_code)

        # Overrides CRUD + base por permisos.modulo.model
        # (La parte de record rules filtra lectura; aquí reforzamos write/create/unlink)
        # Si hay deny explícito en overrides, bloquea.
        return True

    # Hooks CRUD
    def write(self, vals):
        self._check_model_crud('write')
        return super().write(vals)

    def create(self, vals):
        modulo_code = self._modulo_code()
        if modulo_code:
            self.env.user.check_perm(modulo_code, 'crear_registro')
        # self._check_model_crud('create')
        return super().create(vals)


    def unlink(self):
        self._check_model_crud('unlink')
        return super().unlink()
