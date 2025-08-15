from odoo import models, fields, api
from datetime import date

class tasa(models.Model):
    _name = 'tasadeintereses.tasa'
    _rec_name = 'periodo'

    fecha = fields.Date(string = "Periodo", required = True, default = date.today(), store = True)
    tasa = fields.Float(string = "Tasa", required = True, default = "0.0", store = True)
    periodo = fields.Char(string = "Periodo", compute = '_cumpute_periodo', store = True)
    
    @api.depends('fecha')
    def _compute_periodo(self):
        for record in self:
            if record.fecha:
                fecha_dt = fields.Date.to_date(record.fecha)  # Convierte a objeto date
                mes = f"{fecha_dt.month:02d}"  # Formato 2 dígitos (ej: 03)
                anio = str(fecha_dt.year)[-2:]  # Últimos 2 dígitos (ej: 25)
                record.periodo = f"{mes}{anio}"  # Resultado: "0325"
            else:
                record.periodo = False

    _sql_constraints = [
        ('unique_fields_combination', 
         'UNIQUE(periodo)', 
         'Ya existe un registro para este periodo.'),
    ]
