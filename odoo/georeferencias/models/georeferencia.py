from odoo import models, fields

class georeferencias(models.Model):
    _name = "georeferencias.georeferencia"
    _description = "Georeferencias"

    lat = fields.Float(string="Latitud", required=True)
    lon = fields.Float(string="Longitud", required=True)