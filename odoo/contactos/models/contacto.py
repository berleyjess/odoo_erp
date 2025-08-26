# contactos/models/contacto.py
import re
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

PHONE_DIGITS = re.compile(r'\D')
GENERIC_RFC = 'XAXX010101000'

class Contacto(models.Model):
    _name = 'contactos.contacto'
    _description = 'Contacto (rol de persona)'
    _rec_name = 'nombre'

    persona_id = fields.Many2one('persona.persona', string='Persona', index=True, ondelete='restrict')

    # Se ven/teclean en la línea, pero no deben escribir en persona al final
    nombre   = fields.Char(related='persona_id.name',     string='Nombre',   readonly=False)
    telefono = fields.Char(related='persona_id.telefono', string='Teléfono', readonly=False, index=True)
    email    = fields.Char(related='persona_id.email',    string='Email',    readonly=False)

    descripcion = fields.Char(string='Descripción')

    @api.model
    def create(self, vals):
        vals = self._ensure_persona(vals)
        # Impedir que los related empujen cambios a persona al crear
        vals.pop('nombre', None)
        vals.pop('telefono', None)
        vals.pop('email', None)
        return super().create(vals)

    def write(self, vals):
        related_map = {'nombre': 'name', 'telefono': 'telefono', 'email': 'email'}
        to_pop = set()
        for k, pk in related_map.items():
            if k in vals:
                # si el campo en persona está vacío, lo rellenamos allí y NO en el contacto
                empty = not bool(getattr(self.persona_id, pk))
                if empty:
                    v = (vals[k] or '').strip()
                    if k == 'email':
                        v = v.lower()
                    self.persona_id.sudo().write({pk: v or False})
                    to_pop.add(k)
                else:
                    # ya tiene dato en persona → no permitir tocarlo desde el contacto
                    raise ValidationError(_("Edita %s desde la Persona, no desde el contacto.") % k)

        for k in to_pop:
            vals.pop(k, None)

        return super().write(vals)

    # ---- helpers ----
    def _ensure_persona(self, vals):
        """Vincula o crea persona por teléfono/email sin modificar personas existentes."""
        if vals.get('persona_id'):
            return vals

        Person = self.env['persona.persona'].sudo()
        name   = (vals.get('nombre') or '').strip()
        email  = (vals.get('email') or '').strip().lower()
        tel    = (vals.get('telefono') or '').strip()

        digits = re.sub(PHONE_DIGITS, '', tel) if tel else ''
        idx = digits[-10:] if digits else ''

        p = False
        if idx:
            p = Person.search([('telefono_idx', '=', idx)], limit=1)
            if not p and email:
                p = Person.search([('email', '=', email)], limit=1)
        elif email:
            p = Person.search([('email', '=', email)], limit=1)

        if not p and (name or email or tel):
            p = Person.create({
                'name': name or _('SIN NOMBRE'),
                'email': email or False,
                'telefono': tel or False,
                'rfc': GENERIC_RFC,  # RFC genérico para contactos
            })
        if p:
            vals['persona_id'] = p.id
        return vals
