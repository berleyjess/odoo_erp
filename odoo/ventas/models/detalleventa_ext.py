#ventas/models/detalleventa_ext
from odoo import models, fields, api

class detalleventa_ext(models.Model):
    _name='ventas.detalleventa_ext'
    _description = 'Detalle de la Venta de los artículos'
    _inherit = 'detalleventas.detalleventa'

    venta_id = fields.Many2one('ventas.venta', string="Venta", ondelete='cascade')

    @api.onchange('producto')
    def _updateprice(self):
        for record in self:
            if record.producto:
                if record.venta_id.metododepago == 'PUE':
                    record.precio = record.producto.contado
                else:
                    record.precio = record.producto.credito