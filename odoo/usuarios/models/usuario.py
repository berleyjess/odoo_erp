# usuarios/models/res_users.py
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from logging import getLogger
_logger = getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'
    _description = 'Extensión de usuarios para gestión de empresas, sucursales y bodegas.'

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
    bodegas_ids = fields.Many2many(
        'bodegas.bodega', 'res_users_bodegas_rel', 'user_id', 'bodega_id',
        string='Bodegas permitidas'
    )
    bodega_actual_id = fields.Many2one(
        'bodegas.bodega', string='Bodega actual',
        domain="[('id','in', bodegas_ids), ('empresa_id','=', empresa_actual_id)]"
    )

    


    @api.onchange('empresa_actual_id')
    def _onchange_empresa_actual_id(self):
        for u in self:
            if u.sucursal_actual_id and u.sucursal_actual_id.empresa.id != u.empresa_actual_id.id:
                _logger.info("Users: limpiar sucursal_actual por empresa_actual (user=%s)", u.id)
                u.sucursal_actual_id = False
            if u.bodega_actual_id and u.bodega_actual_id.empresa_id.id != u.empresa_actual_id.id:
                _logger.info("Users: limpiar bodega_actual por empresa_actual (user=%s)", u.id)
                u.bodega_actual_id = False



    @api.onchange('empresas_ids')
    def _onchange_empresas_ids(self):
        for u in self:
            if u.sucursales_ids:
                bad_s = u.sucursales_ids.filtered(lambda s: s.empresa.id not in u.empresas_ids.ids)
                if bad_s:
                    u.sucursales_ids = [(3, x) for x in bad_s.ids]
            if u.bodegas_ids:
                bad_b = u.bodegas_ids.filtered(lambda b: b.empresa_id.id not in u.empresas_ids.ids)
                if bad_b:
                    u.bodegas_ids = [(3, x) for x in bad_b.ids]

            if u.empresa_actual_id and u.empresa_actual_id.id not in u.empresas_ids.ids:
                u.empresa_actual_id = False
            if not u.empresa_actual_id and u.empresas_ids:
                u.empresa_actual_id = u.empresas_ids[0]

            if u.sucursal_actual_id and u.sucursal_actual_id.empresa.id not in u.empresas_ids.ids:
                u.sucursal_actual_id = False
            if u.bodega_actual_id and u.bodega_actual_id.empresa_id.id not in u.empresas_ids.ids:
                u.bodega_actual_id = False

    @api.onchange('sucursales_ids')
    def _onchange_sucursales_ids(self):
        for u in self:
            if u.sucursal_actual_id and u.sucursal_actual_id not in u.sucursales_ids:
                u.sucursal_actual_id = False

    @api.onchange('bodegas_ids')
    def _onchange_bodegas_ids(self):
        for u in self:
            if u.bodega_actual_id and u.bodega_actual_id not in u.bodegas_ids:
                u.bodega_actual_id = False
            if u.bodega_actual_id and u.empresa_actual_id and u.bodega_actual_id.empresa_id.id != u.empresa_actual_id.id:
                u.bodega_actual_id = False

    @api.constrains('empresas_ids', 'sucursales_ids', 'bodegas_ids')
    def _check_permitidas(self):
        for u in self:
            bad_s = u.sucursales_ids.filtered(lambda s: s.empresa.id not in u.empresas_ids.ids)
            if bad_s:
                raise ValidationError(_("Hay sucursales que no pertenecen a las empresas permitidas: %s") %
                                      ", ".join(bad_s.mapped('display_name')))
            bad_b = u.bodegas_ids.filtered(lambda b: b.empresa_id.id not in u.empresas_ids.ids)
            if bad_b:
                raise ValidationError(_("Hay bodegas que no pertenecen a las empresas permitidas: %s") %
                                      ", ".join(bad_b.mapped('display_name')))

    @api.constrains('empresa_actual_id', 'sucursal_actual_id', 'bodega_actual_id')
    def _check_actuales_coherentes(self):
        for u in self:
            if u.sucursal_actual_id and u.empresa_actual_id and u.sucursal_actual_id.empresa.id != u.empresa_actual_id.id:
                raise ValidationError(_("La sucursal actual no pertenece a la empresa actual."))
            if u.bodega_actual_id and u.empresa_actual_id and u.bodega_actual_id.empresa_id.id != u.empresa_actual_id.id:
                raise ValidationError(_("La bodega actual no pertenece a la empresa actual."))

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

    @api.constrains('bodega_actual_id')
    def _check_bodega_actual_en_seleccionadas(self):
        for u in self:
            if u.bodega_actual_id and u.bodega_actual_id not in u.bodegas_ids:
                raise ValidationError(_("La bodega actual debe estar en 'Bodegas permitidas'."))
            


    @api.onchange('empresas_ids')
    def _onchange_empresas_ids_set_domain_empresa_actual(self):
        return {'domain': {'empresa_actual_id': [('id', 'in', self.empresas_ids.ids)]}}
    
    @api.onchange('sucursales_ids', 'empresa_actual_id')
    def _onchange_sucursales_ids_set_domain_sucursal_actual(self):
        dom = [('id', 'in', self.sucursales_ids.ids)]
        if self.empresa_actual_id:
            dom.append(('empresa', '=', self.empresa_actual_id.id))
        return {'domain': {'sucursal_actual_id': dom}}
    
    @api.onchange('bodegas_ids', 'empresa_actual_id')
    def _onchange_bodegas_ids_set_domain_bodega_actual(self):
        dom = [('id', 'in', self.bodegas_ids.ids)]
        if self.empresa_actual_id:
            dom.append(('empresa_id', '=', self.empresa_actual_id.id))
        return {'domain': {'bodega_actual_id': dom}}
