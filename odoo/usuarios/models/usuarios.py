from odoo import models, fields

class usuarios(models.Model):
    _inherit = 'res.users'

    sucursales = fields.One2many('sucursales.sucursal', 'usuario_id', string='Sucursales')
    empresas = fields.One2many('empresas.empresa', 'usuario_id', string='Empresas')