from odoo import fields, models, api

class cultivo(models.Model):
    _name='cultivo'

    name=fields.Char(string="Nombre del cultivo", required=True)
    description = fields.Char(string="Descripción")

    @api.model
    def create(self, vals):
        # Convertir a mayúsculas antes de crear
        if 'nombre' in vals:
            vals['name'] = vals['name'].upper() if vals['name'] else False
        if 'description' in vals:
            vals['description'] = vals['description'].upper() if vals['description'] else False
        return super(ccultivo, self).create(vals)

    def write(self, vals):
        # Convertir a mayúsculas antes de actualizar
        if 'name' in vals:
            vals['name'] = vals['name'].upper() if vals['name'] else False
        if 'description' in vals:
            vals['description'] = vals['description'].upper() if vals['description'] else False
        return super(ccultivo, self).write(vals)


