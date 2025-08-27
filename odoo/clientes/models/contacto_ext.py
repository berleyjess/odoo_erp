# clientes/models/contacto_ext.py
# Extiende contactos.contacto para añadir relación con Cliente y marcar un contacto principal (único).
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ContactoExt(models.Model):
    _inherit = 'contactos.contacto'

    cliente_id = fields.Many2one('clientes.cliente', string="Cliente", ondelete='cascade', index=True)
    es_principal = fields.Boolean(string="Principal")

    _sql_constraints = [
        ('uniq_cliente_persona', 'unique(cliente_id, persona_id)',
         'Esta persona ya está agregada como contacto de este cliente.'),
    ]

    @api.constrains('es_principal', 'cliente_id')
    def _check_unico_principal(self):
        for rec in self:
            if rec.es_principal and rec.cliente_id:
                otros = self.search_count([
                    ('id', '!=', rec.id),
                    ('cliente_id', '=', rec.cliente_id.id),
                    ('es_principal', '=', True),
                ])
                if otros:
                    raise ValidationError(_("Ya existe un contacto principal para este cliente."))

    def write(self, vals):
        res = super().write(vals)
        if 'es_principal' in vals:
            for rec in self.filtered(lambda r: r.es_principal and r.cliente_id):
                otros = self.search([
                    ('id', '!=', rec.id),
                    ('cliente_id', '=', rec.cliente_id.id),
                    ('es_principal', '=', True),
                ])
                if otros:
                    otros.write({'es_principal': False})
        return res
