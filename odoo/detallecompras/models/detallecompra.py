from odoo import models, fields, api

class detallecompra(models.Model):
    _name = 'detallecompras.detallecompra'
    _description = 'Detalles/Conceptos de Compras'

    producto = fields.Many2one('productos.producto', string = "Producto", required = True)
    cantidad = fields.Float(string = "Cantidad", required = True)
    precio_unitario = fields.Float(string = "Precio Unitario", required = True)
    subtotal = fields.Float(string = "Subtotal", compute='_compute_subtotal', store=True)
    iva = fields.Float(string = "IVA", compute='_calcimps', help="iva", store = True)
    ieps = fields.Float(string = "IEPS", compute='calcimps', help="ieps", store = True)
    total = fields.Float(string = "Total", compute='_calctotal', store = True)


    @api.depends('cantidad', 'precio_unitario')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.cantidad * record.precio_unitario if record.cantidad and record.precio_unitario else 0.0

    @api.depends('producto')
    def _calimps(self):
        for record in self:
            record.iva = record.producto.iva if record.producto else 0.0
            record.ieps = record.producto.ieps if record.producto else 0.0
            record.precio_unitario = record.producto.precio if record.producto else 0.0

    @api.depends('precio_unitario', 'cantidad', 'producto')
    def _calctotal(self):
        for record in self:
            record.total = (record.precio_unitario * record.cantidad) + (record.iva / 100 * record.precio_unitario) + (record.ieps / 100 * record.precio_unitario) if record.precio_unitario and record.cantidad else 0.0
