from odoo import models, fields

class Empresa(models.Model):
    _inherit = 'empresas.empresa'
    sucursales = fields.One2many('sucursales.sucursal', 'empresa', string="Sucursales")
