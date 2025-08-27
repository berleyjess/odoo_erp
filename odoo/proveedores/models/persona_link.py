# proveedores/models/persona_link.py
# Enlace (rol) entre persona.persona y proveedores.proveedor.
# Smart button / indicadores en Persona.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PersonaLinkProveedor(models.Model):
    _inherit = 'persona.persona'

# One2many “rol proveedor” sobre la persona (delegación via _inherits en el modelo proveedor).
    proveedor_ids = fields.One2many('proveedores.proveedor', 'persona_id', string="Proveedores (rol)")

    # Flag calculado (store=True) para mostrar botón inteligente y permitir dominios/filtrado.
    es_proveedor  = fields.Boolean(compute='_compute_es_proveedor', store=True, string="¿Es proveedor?")

    @api.depends('proveedor_ids')
    def _compute_es_proveedor(self):
        for r in self:
            r.es_proveedor = bool(r.proveedor_ids)

# Acción: abre el proveedor vinculado a la persona o levanta error si no existe.
    def action_open_proveedor(self):
        self.ensure_one()
        prov = self.env['proveedores.proveedor'].search([('persona_id', '=', self.id)], limit=1)
        if not prov:
            raise UserError(_("Esta persona aún no es proveedor. Usa 'Buscar persona por RFC'."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Proveedor'),
            'res_model': 'proveedores.proveedor',
            'view_mode': 'form',
            'res_id': prov.id,
            'target': 'current',
        }
