from odoo import models, field

class predios(models.Model):
    _name = 'predio'

    localidad = fields.Many2one('localidad', string = "Localidad", required = True)
    propietario = fields.Char(string = "Propietario")
    superficie = fields.Float(string = "Superficie")
    registro = fields.Char(string = "Registro")
