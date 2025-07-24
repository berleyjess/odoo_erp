from odoo import models, fields, api

class lineas(models.Model):
    _name = 'lineasdeproducto'
    _description = 'Lineas de productos'

    name = fields.Char(string="Nombre", required=True)
    description = fields.Char(string="Descripción", size=30)

    @api.model
    def create(self, vals):
        # Convertir a mayúsculas antes de crear
        if 'name' in vals:
            vals['name'] = vals['name'].upper() if vals['name'] else False
        if 'description' in vals:
            vals['description'] = vals['description'].upper() if vals['description'] else False
        return super().create(vals)
    @api.model
    def write(self, vals):
        # Convertir a mayúsculas antes de actualizar
        if 'name' in vals:
            vals['name'] = vals['name'].upper() if vals['name'] else False
        if 'description' in vals:
            vals['description'] = vals['description'].upper() if vals['description'] else False
        return super().write(vals)

