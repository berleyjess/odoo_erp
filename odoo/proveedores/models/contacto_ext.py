from odoo import models, fields

class prov_contacto_ext(models.Model):
    _name = 'proveedor.contacto'
    _inherit = 'contacto'

    proveedor_id = fields.Many2one('proveedor', string = "Contactos")
