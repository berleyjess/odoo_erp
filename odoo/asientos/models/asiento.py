from odoo import models, fields

class Cuenta(models.Model):
    _name = 'cuenta'

    longcode = fields.Char(string = "Código")
    codigo = fields.Char(string = "Código")
    descripcion = fields.Char(string = "Descripción", size = 32, required = True)
    padre = fields.Many2one('cuenta')
    child = fields.One2many('cuenta')
