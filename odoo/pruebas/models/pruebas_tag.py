from odoo import models, fields

class PruebasTag(models.Model):
    _name = 'pruebas.tag'
    _description = 'Etiqueta para pruebas'
    name = fields.Char(string='Nombre', required=True)
