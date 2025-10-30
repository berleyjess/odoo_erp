from odoo import models, fields, api

class concepto(models.Model):
    _name = 'ventaconcepto.concepto'
    _description = 'concepto de venta'

    currency_id = fields.Monetary('Moneda', required=True, default=lambda self: self.env.company.currency_id)

    producto_id = fields.Many2one('productos.producto', string="Producto", required=True, store = True)
    cantidad = fields.Float(string="Cantidad", required=True, default=0.000, store = True)
    precio = fields.Monetary(string="Precio Unitario", required=True, default=0.0, store = True)

    iva = fields.Selection(related='producto_id.iva', string="IVA", store=True)
    ieps = fields.Float(related='producto_id.ieps', string="IEPS", store=True)