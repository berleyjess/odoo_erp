from odoo import fields, models

class sucursal(models.Model):
    _name = 'empresas.sucursal'

    empresa = fields.Many2one('empresa', string = "Empresa", ondelete='cascade')
    nombre = fields.Char(string = "Nombre", required = True, size = 30)
    codigo = fields.Char(string = "Prefijo", required = True, size = 2)
    activa = fields.Boolean(string = "Activa", default = True, required = True)
    telefono = fields.Char(string="Teléfono", size = 10)
    calle = fields.Char(string="Calle", size = 30)
    cp = fields.Char(string="Código Postal", size = 5)
   #bodegas = fields.One2many('bodega', 'sucursal', string = "Bodegas")