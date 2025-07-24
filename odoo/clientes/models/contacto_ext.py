from odoo import fields, models

class contactoext(models.Model):
    _name = 'cliente.contacto'
    _inherit = 'contacto'

    cliente_id = fields.Many2one('cliente', string = "Cliente", ondelete = 'cascade')
