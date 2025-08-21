from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
#personas/models/roles.py
class Cliente(models.Model):
    _name = 'persona.cliente'
    _description = 'Rol: Cliente'
    _inherits = {'persona.persona': 'persona_id'}

    persona_id = fields.Many2one('persona.persona', required=True, ondelete='cascade', index=True)
    # Campos específicos de cliente
    #limite_credito = fields.Float()

    _sql_constraints = [
        ('uniq_persona_cliente', 'unique(persona_id)', 'Esta persona ya es Cliente.'),
    ]

    @api.constrains('persona_id')
    def _check_required_cliente(self):
        for rec in self:
            if not rec.curp:  # campo expuesto por _inherits
                raise ValidationError(_("CURP es obligatorio para Cliente."))

class Proveedor(models.Model):
    _name = 'persona.proveedor'
    _description = 'Rol: Proveedor'
    _inherits = {'persona.persona': 'persona_id'}

    persona_id = fields.Many2one('persona.persona', required=True, ondelete='cascade', index=True)
    # Campos específicos de proveedor
    #plazo_pago_dias = fields.Integer()

    _sql_constraints = [
        ('uniq_persona_proveedor', 'unique(persona_id)', 'Esta persona ya es Proveedor.'),
    ]

    @api.constrains('persona_id')
    def _check_required_proveedor(self):
        for rec in self:
            if not rec.rfc:
                raise ValidationError(_("RFC es obligatorio para Proveedor."))

class Empleado(models.Model):
    _name = 'persona.empleado'
    _description = 'Rol: Empleado'
    _inherits = {'persona.persona': 'persona_id'}

    persona_id = fields.Many2one('persona.persona', required=True, ondelete='cascade', index=True)
    # Campos específicos de empleado
    #puesto = fields.Char()
    #salario = fields.Float()

    _sql_constraints = [
        ('uniq_persona_empleado', 'unique(persona_id)', 'Esta persona ya es Empleado.'),
    ]

    @api.constrains('persona_id')
    def _check_required_empleado(self):
        for rec in self:
            if not rec.numero_social:
                raise ValidationError(_("Número social es obligatorio para Empleado."))
