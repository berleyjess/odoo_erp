# contactos/models/phone_lookup_wizard.py (nuevo)
import re
from odoo import models, fields, _, api
from odoo.exceptions import UserError

class PhoneLookupWizard(models.TransientModel):
    _name = 'contactos.phone_lookup_wizard'
    _description = 'Buscar persona por teléfono'

    telefono = fields.Char(string="Teléfono", required=True, help="Acepte 10 dígitos o con separadores; se normaliza.")

    def _digits(self, s):
        return re.sub(r'\D', '', s or '')

    def action_lookup(self):
        self.ensure_one()
        digits = self._digits(self.telefono)
        if not digits:
            raise UserError(_("Captura un teléfono."))
        # Busca persona por el índice
        Person = self.env['persona.persona'].sudo()
        p = Person.search([('telefono_idx', '=', digits)], limit=2)
        if len(p) > 1:
            raise UserError(_("Hay más de una persona con el teléfono %s.") % self.telefono)
        if not p:
            raise UserError(_("No existe una persona con el teléfono %s.") % self.telefono)

        # ¿Ya hay contacto?
        Contacto = self.env['contactos.contacto'].sudo()
        existing = Contacto.search([('persona_id', '=', p.id)], limit=1)
        if existing:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Contacto'),
                'res_model': 'contactos.contacto',
                'view_mode': 'form',
                'res_id': existing.id,
                'target': 'current',
            }

        # Crear nuevo: prellenar persona y (si venimos desde cliente) cliente
        ctx = {
            'default_persona_id': p.id,
        }
        if self.env.context.get('active_model') == 'clientes.cliente' and self.env.context.get('active_id'):
            ctx['default_cliente_id'] = self.env.context['active_id']

        return {
            'type': 'ir.actions.act_window',
            'name': _('Nuevo Contacto'),
            'res_model': 'contactos.contacto',
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }
