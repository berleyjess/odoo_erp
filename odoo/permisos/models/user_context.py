# permisos/models/user_context.py
from odoo import models, fields

class PermUserContext(models.Model):
    _name = 'permisos.user.context'
    _description = 'Contexto de módulo por usuario'
    _sql_constraints = [('uniq_user_mod', 'unique(usuario_id, modulo_id)', 'Contexto duplicado.')]

    usuario_id  = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    modulo_id   = fields.Many2one('permisos.modulo', required=True, ondelete='cascade', index=True)
    empresa_id  = fields.Many2one('empresas.empresa', ondelete='restrict')
    sucursal_id = fields.Many2one('sucursales.sucursal', ondelete='restrict')
    bodega_id   = fields.Many2one('bodegas.bodega', ondelete='restrict')
