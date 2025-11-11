# permisos/models/audit.py
# -*- coding: utf-8 -*-
import json
from odoo import models, fields

AUDIT_MODELS = [
    'permisos.modulo', 'permisos.modulo.model',
    'permisos.permiso', 'permisos.rango',
    'permisos.asignacion.rango', 'permisos.asignacion.permiso',
    'permisos.asignacion.model_crud', 'accesos.acceso'
]

class PermAuditMixin(models.AbstractModel):
    _name = 'permisos.audit.mixin'
    _description = 'Mixin de auditoría simple'

    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec, vals in zip(recs, vals_list):
            rec.env['permisos.audit.log'].sudo().create({
                'action':'create','model': rec._name,'res_id': rec.id,
                'vals_before': "{}", 'vals_after': json.dumps(vals)
            })
        return recs

    def write(self, vals):
        befores = [{f.name: getattr(r, f.name) for f in r._fields.values()
                    if f.store and f.name in vals} for r in self]
        res = super().write(vals)
        for r, b in zip(self, befores):
            r.env['permisos.audit.log'].sudo().create({
                'action':'write','model': r._name,'res_id': r.id,
                'vals_before': json.dumps(b), 'vals_after': json.dumps(vals)
            })
        return res

    def unlink(self):
        for r in self:
            r.env['permisos.audit.log'].sudo().create({
                'action':'unlink','model': r._name,'res_id': r.id,
                'vals_before': json.dumps({'display_name': r.display_name}), 'vals_after': "{}"
            })
        return super().unlink()


class PermAuditLog(models.Model):
    _name = 'permisos.audit.log'
    _description = 'Auditoría de cambios en seguridad'
    _order = 'create_date desc'

    when = fields.Datetime(default=lambda s: fields.Datetime.now(), string='Fecha/hora')
    user_id = fields.Many2one('res.users', default=lambda s: s.env.user, string='Usuario')
    action = fields.Selection([('create','Create'),('write','Write'),('unlink','Unlink')], string='Acción')
    model = fields.Char()
    res_id = fields.Integer()
    vals_before = fields.Text()
    vals_after  = fields.Text()
    origin = fields.Char(default='form')


"""
en cada modelo que se quiera auditar, añade:
class PermAsignacionRango(models.Model):
    _name = 'permisos.asignacion.rango'
    _inherit = ['permisos.audit.mixin']
    ...

Es explícito y no rompe el registry.

"""