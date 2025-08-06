from odoo import models, fields, api, _
from odoo.exceptions import ValidationError  

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

    @api.constrains('finicio', 'ffinal')
    def _check_dates(self):
        for rec in self:
            # Permite igualdad; cambia < por <= si quieres obligar que sea estrictamente mayor
            if rec.finicio and rec.ffinal and rec.ffinal < rec.finicio:
                raise ValidationError(
                    #El "_" sirve para traducir el mensaje, simplemente se puede poner la cadena sin el "_" si no se quiere traducir.
                    _("La Fecha Final (%s) no puede ser menor que la Fecha de Inicio (%s).") %
                    (rec.ffinal, rec.finicio)
                )
            
    _sql_constraints = [
        ('unique_label', 'unique(label)', 'Ya existe un ciclo con ese periodo y rango de años.')
    ]
