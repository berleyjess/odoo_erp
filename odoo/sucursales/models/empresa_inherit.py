# sucursales/models/empresa_inherit.py
from odoo import models, fields

class Empresa(models.Model):
    _inherit = 'empresas.empresa'
    sucursal_ids = fields.One2many(
        'sucursales.sucursal', 'empresa', string="Sucursales"
    )
