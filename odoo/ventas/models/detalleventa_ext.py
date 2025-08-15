#ventas/models/detalleventa_ext
from odoo import models, fields, api
# Extiende el modelo detalleventas.detalleventa para asociarlo a una venta
class detalleventa_ext(models.Model):
    _name='ventas.detalleventa_ext'
    _description = 'Detalle de la Venta de los artículos'
    _inherit = 'detalleventas.detalleventa'

    venta_id = fields.Many2one('ventas.venta', string="Venta", ondelete='cascade')
# Ajusta el precio según el método de pago (contado/crédito)
    @api.onchange('producto', 'venta_id.metododepago')
    def _updateprice(self):
        for record in self:
            if record.producto:
                metodo = record.venta_id.metododepago or 'PPD'
                record.precio = record.producto.contado if metodo == 'PUE' else record.producto.credito
