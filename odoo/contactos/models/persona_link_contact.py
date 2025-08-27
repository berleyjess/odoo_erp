# contactos/models/persona_link_contact.py 
import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PersonaLinkContact(models.Model):
    _inherit = 'persona.persona'

    contacto_ids = fields.One2many('contactos.contacto', 'persona_id', string="Contactos")
    es_contacto = fields.Boolean(compute='_compute_es_contacto', store=True)

    @api.depends('contacto_ids')
    def _compute_es_contacto(self):
        for r in self:
            r.es_contacto = bool(r.contacto_ids)

    def action_open_contacto(self):
        self.ensure_one()
        c = self.env['contactos.contacto'].search([('persona_id', '=', self.id)], limit=1)
        if not c:
            raise UserError(_("Esta persona aún no tiene contacto. Usa 'Crear/Buscar contacto por teléfono'."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contacto'),
            'res_model': 'contactos.contacto',
            'view_mode': 'form',
            'res_id': c.id,
            'target': 'current',
        }

    def action_check_tel_contacto(self):
        """Abre el wizard de teléfono desde persona (prellenado)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Buscar contacto por teléfono'),
            'res_model': 'contactos.phone_lookup_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_telefono': self.telefono or ''},
        }
