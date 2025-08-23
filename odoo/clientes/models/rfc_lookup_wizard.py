from odoo import models, fields, _
from odoo.exceptions import UserError

class RfcLookupWizard(models.TransientModel):
    _name = 'clientes.rfc_lookup_wizard'
    _description = 'Buscar persona por RFC'

    rfc = fields.Char(string="RFC", required=True)

    def action_lookup(self):
        self.ensure_one()
        r = (self.rfc or '').strip().upper()
        if not r:
            raise UserError(_("Captura el RFC."))

        Person = self.env['persona.persona'].sudo()
        p = Person.search([('rfc', '=', r)], limit=2)
        if len(p) > 1:
            raise UserError(_("Hay más de una persona con el RFC %s.") % r)
        if not p:
            raise UserError(_("No existe una persona con el RFC %s.") % r)

        Cliente = self.env['clientes.cliente'].sudo()
        existing = Cliente.search([('persona_id', '=', p.id)], limit=1)
        if existing:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Cliente'),
                'res_model': 'clientes.cliente',
                'view_mode': 'form',
                'res_id': existing.id,
                'target': 'current',
            }
        # abrir creación prellenando persona
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nuevo Cliente'),
            'res_model': 'clientes.cliente',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_persona_id': p.id,
                'default_rfc': p.rfc,
                'default_nombre': p.name,
            },
        }

