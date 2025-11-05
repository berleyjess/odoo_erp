# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class Acceso(models.Model):
    _name = 'accesos.acceso'
    _description = 'Asignación de accesos a usuarios'
    _rec_name = 'codigo'
    _order = 'id desc'
    _check_company_auto = False  # usamos empresas.empresa, no res.company

    codigo = fields.Char(string='Código', readonly=True, copy=False, default='Nuevo', index=True)

    usuario_id = fields.Many2one(
        'res.users', string='Usuario', required=True, ondelete='restrict', index=True
    )
    empresa_id = fields.Many2one(
        'empresas.empresa', string='Empresa', required=True, ondelete='restrict', index=True
    )
    bodega_id = fields.Many2one(
        'bodegas.bodega', string='Bodega', required=True, ondelete='restrict', index=True
    )

    # Permisos como checks
    can_read = fields.Boolean(string='Leer')
    can_write = fields.Boolean(string='Editar')
    can_create = fields.Boolean(string='Crear')
    is_admin = fields.Boolean(string='Administrador')

    active = fields.Boolean(default=True, string="Activo")

    _sql_constraints = [
        (
            'acceso_unique_user_emp_bod',
            'unique(usuario_id, empresa_id, bodega_id)',
            'Ya existe un acceso para ese Usuario/Empresa/Bodega.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('codigo', 'Nuevo') in (False, 'Nuevo'):
                vals['codigo'] = seq.next_by_code('accesos.acceso') or '/'
        recs = super().create(vals_list)
        return recs

    @api.onchange('is_admin')
    def _onchange_is_admin(self):
        for r in self:
            if r.is_admin:
                r.can_read = True
                r.can_write = True
                r.can_create = True

    @api.constrains('can_read', 'can_write', 'can_create', 'is_admin')
    def _check_some_permission(self):
        for r in self:
            if not (r.can_read or r.can_write or r.can_create or r.is_admin):
                raise ValidationError(_('Debes marcar al menos un permiso (o Administrador).'))
