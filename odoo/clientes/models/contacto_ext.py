from odoo import fields, models

class contactoext(models.Model):
    _name = 'clientes.contacto_ext'
    _inherit = 'contactos.contacto'  # Hereda del modelo de contactos existente

    # CORREGIDO: Debe apuntar a 'clientes.cliente' no a 'clientes.contacto'
    cliente_id = fields.Many2one('clientes.cliente', string="Cliente", ondelete='cascade')