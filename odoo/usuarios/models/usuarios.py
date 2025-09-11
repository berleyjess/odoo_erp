# usuarios/models/res_users.py
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ResUsers(models.Model):
    _inherit = 'res.users'

    empresas_ids = fields.Many2many(
        'empresas.empresa', 'res_users_empresas_rel', 'user_id', 'empresa_id',
        string='Empresas permitidas'
    )
    sucursales_ids = fields.Many2many(
        'sucursales.sucursal', 'res_users_sucursales_rel', 'user_id', 'sucursal_id',
        string='Sucursales permitidas'
    )

    empresa_actual_id = fields.Many2one(
        'empresas.empresa', string='Empresa actual',
        domain="[('id','in', empresas_ids)]"
    )
    sucursal_actual_id = fields.Many2one(
        'sucursales.sucursal', string='Sucursal actual',
        domain="[('id','in', sucursales_ids), ('empresa','=', empresa_actual_id)]"
    )

    @api.onchange('empresa_actual_id')
    def _onchange_empresa_actual_id(self):
        for u in self:
            if u.sucursal_actual_id and u.sucursal_actual_id.empresa != u.empresa_actual_id:
                u.sucursal_actual_id = False

    @api.onchange('empresas_ids')
    def _onchange_empresas_ids(self):
        # Si quitan empresas, limpia sucursales que ya no correspondan
        for u in self:
            if u.sucursales_ids:
                u.sucursales_ids = [(3, s.id) for s in u.sucursales_ids if s.empresa not in u.empresas_ids]
            if u.empresa_actual_id and u.empresa_actual_id not in u.empresas_ids:
                u.empresa_actual_id = False
            if u.sucursal_actual_id and u.sucursal_actual_id.empresa not in u.empresas_ids:
                u.sucursal_actual_id = False

    @api.constrains('empresas_ids', 'sucursales_ids')
    def _check_sucursales_permitidas(self):
        for u in self:
            bad = u.sucursales_ids.filtered(lambda s: s.empresa not in u.empresas_ids)
            if bad:
                raise ValidationError(_("Hay sucursales que no pertenecen a las empresas permitidas: %s") %
                                      ", ".join(bad.mapped('display_name')))
