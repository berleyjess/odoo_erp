# contactos.models.contacto.py
from odoo import models, fields, api

class contacto(models.Model):
    _name = 'contactos.contacto'
    _description = 'Modelo para gestionar contacto de clientes y proveedores'

    nombre = fields.Char(string = "Nombre", size = 32, required = True)
    telefono = fields.Char(string = "Teléfono", size = 10, required = True)
    descripcion = fields.Char(string = "Descripción", size = 32)
    email = fields.Char(string = "Email", size = 32)

    @api.model
    def create(self, vals):
        # Convertir a mayúsculas antes de crear
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].upper() if vals['nombre'] else False
        return super().create(vals)

    def write(self, vals):

        # Convertir a mayúsculas antes de actualizar
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].upper() if vals['nombre'] else False
        return super().write(vals)