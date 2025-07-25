from odoo import models, fields, api

class ciclo(models.Model):
    _name = 'ciclos.ciclo'
    _description = 'Ciclos Agrícolas'
    _rec_name = 'label'

    periodo = fields.Selection(selection=
                               [
                                  ("OI", "Otoño-Invierno"),
                                  ("PV", "Primavera-Verano")
                               ], string="Periodo", required=True)
    finicio = fields.Date(string="Fecha de Inicio", required=True)
    ffinal = fields.Date(string="Fecha Final", required=True)

    label = fields.Char(compute='_deflabel', store = True, string="Ciclo")
    
    @api.depends('periodo', 'finicio', 'ffinal')
    def _deflabel(self):
        for record in self:
            periodo = record.periodo or ''
            anio_inicio = record.finicio.year if record.finicio else ''
            anio_final = record.ffinal.year if record.ffinal else ''
            if periodo and anio_inicio and anio_final:
                record.label = f"{periodo} {anio_inicio}-{anio_final}"
            else:
                record.label = ''

    _sql_constraints = [
        ('unique_label', 'unique(label)', 'Ya existe un ciclo con ese periodo y rango de años.')
    ]


