from odoo import api, fields, models, _
from odoo.exceptions import UserError
#personas/wizard/role_promote_wizard
class RolePromoteWizard(models.TransientModel):
    _name = 'persona.role.promote.wizard'
    _description = 'Promover Persona a Rol'

    rol = fields.Selection([
        ('cliente', 'Cliente'),
        ('proveedor', 'Proveedor'),
        ('empleado', 'Empleado')
    ], required=True)

    nombre = fields.Char(string="Nombre de la persona")  # por si hay que crear
    rfc = fields.Char()
    curp = fields.Char()
    numero_social = fields.Char()

    persona_id = fields.Many2one('persona.persona', string="Coincidencia detectada", readonly=True)

    @api.onchange('rfc', 'curp', 'numero_social')
    def _onchange_ident(self):
        dom = ['|','|', ('rfc','=', self.rfc or False),
                        ('curp','=', self.curp or False),
                        ('numero_social','=', self.numero_social or False)]
        self.persona_id = self.env['persona.persona'].search(dom, limit=1)

    def action_apply(self):
        Persona = self.env['persona.persona']
        if not self.persona_id:
            if not (self.rfc or self.curp or self.numero_social):
                raise UserError(_("Indica al menos RFC, CURP o Número Social para buscar/crear."))
            if not self.nombre:
                raise UserError(_("Indica el Nombre para crear la persona."))
            self.persona_id = Persona.create({
                'name': self.nombre,
                'rfc': self.rfc,
                'curp': self.curp,
                'numero_social': self.numero_social,
            })

        p = self.persona_id
        if self.rol == 'cliente':
            rec = self.env['persona.cliente'].create({'persona_id': p.id})
            action_xmlid = 'persona_base.action_clientes'
            model = 'persona.cliente'
        elif self.rol == 'proveedor':
            rec = self.env['persona.proveedor'].create({'persona_id': p.id})
            action_xmlid = 'persona_base.action_proveedores'
            model = 'persona.proveedor'
        else:
            rec = self.env['persona.empleado'].create({'persona_id': p.id})
            action_xmlid = 'persona_base.action_empleados'
            model = 'persona.empleado'

        # Abrir el registro creado
        return {
            'type': 'ir.actions.act_window',
            'res_model': model,
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
        }
