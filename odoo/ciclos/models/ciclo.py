from odoo import models, fields, api

class ciclo(models.Model):
    _name = 'ciclo'
    _description = 'Ciclos Agrícolas'

    name = fields.Char(string="Nombre", required=True)
    f_inicio = fields.Date(string="Fecha de Inicio", required=True)
    f_final = fields.Date(string="Fecha Final", required=True)

    @api.model
    def create(self, vals):
        # Convertir a mayúsculas antes de crear
        if 'name' in vals:
            vals['name'] = vals['name'].upper() if vals['name'] else False
        return super(ciclo, self).create(vals)

    def write(self, vals):
        # Convertir a mayúsculas antes de actualizar
        if 'name' in vals:
            vals['name'] = vals['name'].upper() if vals['name'] else False
        return super(ciclo, self).write(vals)

