from odoo import models, fields

class georeferencias(models.Model):
    _name = "georeferencias.georeferencia"
    _description = "Georeferencias"

    lat = fields.Float(string="Latitud", required=True, digits=(16, 5))
    lon = fields.Float(string="Longitud", required=True, digits=(16, 5))