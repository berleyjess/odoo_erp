# usuarios/models/res_users.py
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ResUsers(models.Model):
    _inherit = 'res.users'
    _description = 'Extensión de usuarios para gestión de empresas y sucursales.'

    empresas_ids = fields.Many2many(
        'empresas.empresa', 'res_users_empresas_rel', 'user_id', 'empresa_id',
        string='Empresas permitidas'
    )
    sucursales_ids = fields.Many2many(
        'sucursales.sucursal', 'res_users_sucursales_rel', 'user_id', 'sucursal_id',
        string='Sucursales permitidas'
    )
    empresa_actual_id = fields.Many2one(
        'empresas.empresa',
        string='Empresa actual',
    )
    sucursal_actual_id = fields.Many2one(
        'sucursales.sucursal',
        string='Sucursal actual',
)


    @api.onchange('empresa_actual_id')
    def _onchange_empresa_actual_id(self):
        for u in self:
            if u.sucursal_actual_id and u.sucursal_actual_id.empresa.id != u.empresa_actual_id.id:
                u.sucursal_actual_id = False

    @api.onchange('empresas_ids')
    def _onchange_empresas_ids(self):
        for u in self:
            # Limpiar sucursales que no pertenezcan a empresas elegidas
            if u.sucursales_ids:
                bad = u.sucursales_ids.filtered(lambda s: s.empresa.id not in u.empresas_ids.ids)
                if bad:
                    u.sucursales_ids = [(3, x) for x in bad.ids]
            # Si quitaron la empresa actual, reset
            if u.empresa_actual_id and u.empresa_actual_id.id not in u.empresas_ids.ids:
                u.empresa_actual_id = False
            # UX: si hay empresas y no hay empresa_actual, proponer la primera
            if not u.empresa_actual_id and u.empresas_ids:
                u.empresa_actual_id = u.empresas_ids[0]
            # Si la sucursal actual ya no está permitida, reset
            if u.sucursal_actual_id and u.sucursal_actual_id.empresa.id not in u.empresas_ids.ids:
                u.sucursal_actual_id = False

    @api.onchange('sucursales_ids')
    def _onchange_sucursales_ids(self):
        for u in self:
            if u.sucursal_actual_id and u.sucursal_actual_id not in u.sucursales_ids:
                u.sucursal_actual_id = False

    @api.constrains('empresas_ids', 'sucursales_ids')
    def _check_sucursales_permitidas(self):
        for u in self:
            bad = u.sucursales_ids.filtered(lambda s: s.empresa.id not in u.empresas_ids.ids)
            if bad:
                raise ValidationError(_("Hay sucursales que no pertenecen a las empresas permitidas: %s") %
                                      ", ".join(bad.mapped('display_name')))

    @api.constrains('empresa_actual_id', 'sucursal_actual_id')
    def _check_actuales_coherentes(self):
        for u in self:
            if u.sucursal_actual_id and u.empresa_actual_id and \
               u.sucursal_actual_id.empresa.id != u.empresa_actual_id.id:
                raise ValidationError(_("La sucursal actual no pertenece a la empresa actual."))



    @api.onchange('empresas_ids', 'sucursales_ids', 'empresa_actual_id')
    def _onchange_apply_domains(self):
        for u in self:
            if u.empresa_actual_id and u.empresa_actual_id.id not in u.empresas_ids.ids:
                u.empresa_actual_id = False
            if u.sucursal_actual_id:
                invalid_by_ids = u.sucursal_actual_id.id not in u.sucursales_ids.ids
                invalid_by_company = (u.empresa_actual_id and u.sucursal_actual_id.empresa.id != u.empresa_actual_id.id)
                if invalid_by_ids or invalid_by_company:
                    u.sucursal_actual_id = False
        return

    @api.constrains('empresa_actual_id')
    def _check_empresa_actual_en_seleccionadas(self):
        for u in self:
            if u.empresa_actual_id and u.empresa_actual_id not in u.empresas_ids:
                raise ValidationError(_("La empresa actual debe estar en 'Empresas permitidas'."))

    @api.constrains('sucursal_actual_id')
    def _check_sucursal_actual_en_seleccionadas(self):
        for u in self:
            if u.sucursal_actual_id and u.sucursal_actual_id not in u.sucursales_ids:
                raise ValidationError(_("La sucursal actual debe estar en 'Sucursales permitidas'."))       

        # === Helpers de permisos aplicables al proyecto ===
    def has_perm(self, modulo_code, permiso_code, empresa_id=None, sucursal_id=None, bodega_id=None):
        return super(ResUsers, self).has_perm(modulo_code, permiso_code, empresa_id=empresa_id, sucursal_id=sucursal_id, bodega_id=bodega_id)

    def check_perm(self, modulo_code, permiso_code, empresa_id=None, sucursal_id=None, bodega_id=None):
        return super(ResUsers, self).check_perm(modulo_code, permiso_code, empresa_id=empresa_id, sucursal_id=sucursal_id, bodega_id=bodega_id)
