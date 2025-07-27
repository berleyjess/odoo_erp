from odoo import models, fields

class georeferencia_ext(models.Model):
    _name = 'predios.georeferencia_ext'
    _description = 'Georeferencia para predios'
    _inherit = 'georeferencias.georeferencia'

    predio_id = fields.Many2one('predios.predio', string="Predio", required=True)