#clientes.models.contacto_ext.py
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class contactoext(models.Model):
    _inherit = 'contactos.contacto'  # Hereda del modelo de contactos existente
    cliente_id = fields.Many2one('clientes.cliente', string="Cliente", ondelete='cascade')

    # NUEVO: marcar un contacto como principal
    es_principal = fields.Boolean(string="Principal")

    @api.constrains('es_principal', 'cliente_id')
    def _check_unico_principal(self):
        for rec in self:
            if rec.es_principal and rec.cliente_id:
                otros = self.search_count([
                    ('id', '!=', rec.id),
                    ('cliente_id', '=', rec.cliente_id.id),
                    ('es_principal', '=', True)
                ])
                if otros:
                    raise ValidationError(_("Ya existe un contacto principal para este cliente."))

    def write(self, vals):
        res = super().write(vals)
        # Si marco este como principal, desmarco otros (por si ya existían)
        if 'es_principal' in vals and any(self.mapped('es_principal')):
            for rec in self.filtered(lambda r: r.es_principal and r.cliente_id):
                otros = self.search([
                    ('id', '!=', rec.id),
                    ('cliente_id', '=', rec.cliente_id.id),
                    ('es_principal', '=', True)
                ])
                if otros:
                    otros.write({'es_principal': False})
        return res