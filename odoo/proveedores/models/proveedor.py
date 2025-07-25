from odoo import models, fields, api

class proveedores(models.Model):
    _name = 'proveedor'

    nombre = fields.Char(string = "Razón Social", required = True)
    rfc = fields.Char(string = "RFC", required = True)
    localidad = fields.Many2one('localidad', string = "Ciudad")
    calle = fields.Char(string = "Calle")
    numero = fields.Char(string = "Número")
    codigop = fields.Char(string = "Código Postal", size = 5)
    descripcion = fields.Char(string = "Descripción")

    contacto = fields.One2many('proveedor.contacto', 'proveedor_id', string = "Contactos")

    codigo = fields.Char( #Código interno del Cliente
        string='Código',
        size=10,
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_code()
        #help="Código único autogenerado con formato COD-000001"
    )

    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_proov_code') or '/'
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
