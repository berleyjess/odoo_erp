# proveedores/models/rfc_lookup_wizard.py
from odoo import models, fields, _
from odoo.exceptions import UserError

class RfcLookupWizardProveedor(models.TransientModel):
    _name = 'proveedores.rfc_lookup_wizard'
    _description = 'Buscar persona por RFC (Proveedor)'

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

        Prov = self.env['proveedores.proveedor'].with_context(active_test=False).sudo()
        existing = Prov.search([('persona_id', '=', p.id)], limit=1)
        if existing:
            if not existing.active:
                existing.sudo().write({'active': True})
            return {
                'type': 'ir.actions.act_window',
                'name': _('Proveedor'),
                'res_model': 'proveedores.proveedor',
                'view_mode': 'form',
                'res_id': existing.id,
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Nuevo Proveedor'),
            'res_model': 'proveedores.proveedor',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_persona_id': p.id,
                'default_rfc': p.rfc,
                'default_nombre': p.name,
            },
        }
