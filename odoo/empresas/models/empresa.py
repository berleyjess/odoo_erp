from odoo import fields, models, api

class empresa(models.Model):
    _name = 'empresas.empresa'
    _description = "Modelo de Empresa, almacena el catálogo de empresas."

    nombre = fields.Char(string = "Nombre", required = True, size = 50)
    descripcion = fields.Char(string = "Descripción", size = 50)
    telefono = fields.Char(string = "Teléfono", size = 10)
    razonsocial = fields.Char(string = "Razón Social", required = True)
    rfc = fields.Char(string = "RFC", required = True, size = 14)
    cp = fields.Char(string = "Código Postal", required = True)
    calle = fields.Char(string = "Calle", size = 20)
    numero = fields.Char(string = "Número", size = 32)
    sucursales = fields.One2many('sucursal', 'empresa', string = "Sucursales")
    bodegas = fields.One2many('bodega', 'empresa', string="Bodegas", ondelete='cascade')
    codigo = fields.Char(
        string='Código',
        size=10,
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_code(),
        #help="Código único autogenerado con formato COD-000001"
    )
    
    @api.depends('sucursales.bodegas')
    def _compute_bodegas(self):
        for empresa in self:
            empresa.bodegas = empresa.sucursals.mapped('bodegas')

    @api.model
    def create(self, vals):
        # Convertir a mayúsculas antes de crear
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].upper() if vals['nombre'] else False
        if 'razonsocial' in vals:
            vals['razonsocial'] = vals['razonsocial'].upper() if vals['razonsocial'] else False
        if 'rfc' in vals:
            vals['rfc'] = vals['rfc'].upper() if vals['rfc'] else False
        return super().create(vals)

    def write(self, vals):
        # Convertir a mayúsculas antes de actualizar
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].upper() if vals['nombre'] else False
        if 'razonsocial' in vals:
            vals['razonsocial'] = vals['razonsocial'].upper() if vals['razonsocial'] else False
        if 'rfc' in vals:
            vals['rfc'] = vals['rfc'].upper() if vals['rfc'] else False
        return super().write(vals)

    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_emp_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(2)}"