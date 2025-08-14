from odoo import models, fields, api
from datetime import date

class tasa(models.Model):
    _name = 'tasadeintereses.tasa'

    periodo = fields.Date(string = "Periodo", required = True, default = date.today(), store = True)
    tasa = fields.Date(string = "Tasa", required = True, default = "0.0", store = True)

    _sql_constraints = [
        ('unique_fields_combination', 
         'UNIQUE(periodo, tasa)', 
         'Ya existe un registro para este periodo.'),
    ]
