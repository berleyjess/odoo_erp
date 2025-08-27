# clientes/models/persona_link.py

# Añade rol "Cliente" a persona.persona: smart button y flag es_cliente (compute).

from odoo import api, fields, models
from odoo import _
from odoo.exceptions import UserError

class PersonaLink(models.Model):
    _inherit = 'persona.persona'

    #el One2many a clientes.cliente (personas → sus clientes).
    cliente_ids = fields.One2many(
        'clientes.cliente', 'persona_id', string="Clientes (rol)"
    )
    #booleano calculado que indica si la persona tiene al menos un cliente.
    es_cliente = fields.Boolean(
        compute='_compute_es_cliente', string="¿Es cliente?", store=True
    )

    def action_open_cliente(self):
        self.ensure_one()
        cliente = self.env['clientes.cliente'].search([('persona_id', '=', self.id)], limit=1)
        if not cliente:
            raise UserError(_("Esta persona aún no es cliente. Usa 'Crear/Buscar cliente por RFC'."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cliente'),
            'res_model': 'clientes.cliente',
            'view_mode': 'form',
            'res_id': cliente.id,
            'target': 'current',
        }
    @api.depends('cliente_ids')
    def _compute_es_cliente(self):
        for rec in self:
            rec.es_cliente = bool(rec.cliente_ids)



    def action_check_rfc_cliente(self):
        self.ensure_one()
        rfc = (self.rfc or '').strip().upper()
        if not rfc:
            raise UserError(_("Captura el RFC primero para poder buscarlo."))

        Cliente = self.env['clientes.cliente'].sudo()

        # 1) ¿Ya hay cliente ligado a esta persona?
        cliente = Cliente.search([('persona_id', '=', self.id)], limit=1)

        # 2) Si no, busca por RFC vía persona relacionada
        if not cliente:
            encontrados = Cliente.search([('persona_id.rfc', '=', rfc)], limit=2)
            if len(encontrados) > 1:
                raise UserError(_("Hay más de un cliente con el RFC %s. Revisa duplicados.") % rfc)
            cliente = encontrados[:1]

        # 3) Abre existente o abre formulario para crear (prellenado)
        if cliente:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Cliente'),
                'res_model': 'clientes.cliente',
                'view_mode': 'form',
                'res_id': cliente.id,
                'target': 'current',
            }

        ctx = {
            'default_persona_id': self.id,   # suficiente para prellenar related
            'default_nombre': self.name,
            'default_rfc': rfc,
        }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nuevo Cliente'),
            'res_model': 'clientes.cliente',
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }