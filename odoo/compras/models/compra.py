from odoo import models, fields

class compra(models.Model):
    _name = 'compras.compra'
    _description="Modelo para compras"

    fecha = fields.Date(string = "Fecha", default=fields.Date.context_today, required=True)
    proveedor = fields.Many2one('proveedores.proveedor', string='Proveedor', required=True)

    detalle = fields.One2many('compras.detallecompra_ext', 'compra_id', string="Detalles de Compra")

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
        sequence = self.env['ir.sequence'].next_by_code('seq_compra_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(6)}"
