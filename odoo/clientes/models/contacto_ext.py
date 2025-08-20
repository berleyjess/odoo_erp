#clientes.models.contacto_ext.py
from odoo import fields, models

class contactoext(models.Model):
    _inherit = 'contactos.contacto'  # Hereda del modelo de contactos existente
    cliente_id = fields.Many2one('clientes.cliente', string="Cliente", ondelete='cascade')