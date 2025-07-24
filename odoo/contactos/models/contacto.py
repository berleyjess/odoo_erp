from odoo import models, fields

class contacto(models.Model):
    _name = 'contactos.contacto'

    nombre = fields.Char(string = "Nombre", size = 32, required = True)
    telefono = fields.Char(string = "Teléfono", size = 10, required = True)
    descripcion = fields.Char(string = "Descripción", size = 32)
    email = fields.Char(string = "Email", size = 32)