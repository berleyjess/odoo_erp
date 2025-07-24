from odoo import models, fields, api

class cliente(models.Model):
    _name='cliente'
    _description='Cartera de clientes'
    
    codigo = fields.Char( #Código interno del Cliente
        string='Código',
        size=10,
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_code()
        #help="Código único autogenerado con formato COD-000001"
    )

    nombre = fields.Char(string="Nombre", required=True)

    rfc = fields.Char(string="RFC",size=12)
    tipo = fields.Selection(
        selection = [
            ("0", "Persona Física"),
            ("1", "Persona Moral")
        ], string="Tipo de Cliente", required=True, default = "0"
    )

    regimen = fields.Many2one('c_regimenfiscal',
                              string = "Régimen Fiscal",
                              domain="[('tipo', 'in', [tipo == '0' and '0' or '1', '2'])]"
    )

    codigop = fields.Char(string="Código Postal", size=5)
    localidad = fields.Many2one('localidad', string = "Ciudad/Localidad")
    colonia = fields.Char(string = "Colonia", size = 32)
    calle = fields.Char(string = "Calle", size = 32)
    numero = fields.Char(string = "Número", size = 4)

    contacto = fields.One2many('cliente.contacto', 'cliente_id', string = "Contactos")

    @api.onchange('tipo')
    def _onchange_tipo(self):
        """Actualiza dominio del campo regimen fiscal dinámicamente"""
        if not self.tipo:
            # Resetear el campo si tipo está vacío
            self.regimen = False
            return {'domain': {'regimen': []}}
        
        # Definir dominio basado en el tipo seleccionado
        domain_map = {
            '0': ['0', '2'],  # Persona Física
            '1': ['1', '2']   # Persona Moral
        }
        return {
            'domain': {
                'regimen': [('tipo', 'in', domain_map.get(self.tipo, []))]
            },
            'warning': {
                'title': "Cambio de Régimen Fiscal",
                'message': "Verifique que el RFC coincida con el tipo seleccionado"
            } if self.rfc else None
        }
    
    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_client_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(6)}"
    
    @api.model
    def create(self, vals):
        # Convertir a mayúsculas antes de crear
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].upper() if vals['nombre'] else False
        if 'rfc' in vals:
            vals['rfc'] = vals['rfc'].upper() if vals['rfc'] else False
        return super().create(vals)

    def write(self, vals):
        # Convertir a mayúsculas antes de actualizar
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].upper() if vals['nombre'] else False
        if 'rfc' in vals:
            vals['rfc'] = vals['rfc'].upper() if vals['rfc'] else False
        return super().write(vals)

    def action_save(self):
        return {'type': 'ir.actions.act_window_close'}
    
    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}

    
