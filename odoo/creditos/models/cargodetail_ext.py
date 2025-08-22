from odoo import models, fields
from datetime import date

class cargodetail_ext(models.Model):
    inheirt = 'cargosdetail.cargo'

    fecha = fields.Date(string = "Fecha", default = date.today(), store = True)
    credito_id = fields.Many2one('creditos.credito', "Crédito", store = True)