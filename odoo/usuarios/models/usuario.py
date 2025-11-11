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
    bodegas_ids = fields.Many2many(
        'bodegas.bodega', 'res_users_bodegas_rel', 'user_id', 'bodega_id',
        string='Bodegas permitidas'
    )

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

