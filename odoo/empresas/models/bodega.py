from odoo import models, fields, api

class bodega(models.Model):
    _name = 'empresas.bodega'
    _description = "Modelo de Bodega, almacena el catálogo de bodegas."

    empresa = fields.Many2one(
        'empresas.empresa', string='Empresa',
        required=True, ondelete='restrict', index=True
    )    
    #sucursal_id = fields.Many2one('sucursales.sucursal', string='Sucursal', ondelete='restrict', index=True)
    nombre = fields.Char(string = "Nombre", required = True, size = 20)
    activa = fields.Boolean(string="Activa", required = True, default = True)
    codigo = fields.Char(
        string='Código',
        size=10,
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_code(),
        #help="Código único autogenerado con formato COD-000001"
    )

    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_bod_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(2)}"