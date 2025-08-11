from odoo import models, fields

class stock(models.Model):
    _name = 'stocks.stock'

    producto_id = fields.Many2one('productos.producto', string = "Producto", required = True, store = True)
    sucursal_id = fields.Many2One('sucursales.sucursal', string = "Sucursal", required = True, store = True)
    cantidad = fields.Float(string = "Cantidad", required = True, store = True, default = '0.000')
    