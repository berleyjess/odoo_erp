from odoo import models, fields, api

class DetalleCompra(models.Model):
    _name = 'detallecompras.detallecompra'
    _description = 'Detalles/Conceptos de Compras'

    producto = fields.Many2one('productos.producto', string="Producto", required=True)
    cantidad = fields.Float(string="Cantidad", required=True, default=1.0)
    precio_unitario = fields.Float(string="Precio Unitario", required=True, default=0.0)

    subtotal = fields.Float(string="Subtotal", compute='_compute_subtotal', store=True)
    iva = fields.Float(string="IVA (%)", compute='_compute_impuestos', store=True)
    ieps = fields.Float(string="IEPS (%)", compute='_compute_impuestos', store=True)
    total = fields.Float(string="Total", compute='_compute_total', store=True)

    @api.onchange('producto')
    def _onchange_producto(self):
        if self.producto:
            # usa costo como precio de compra
            self.precio_unitario = float(self.producto.costo or 0.0)

    @api.depends('producto')
    def _compute_impuestos(self):
        for rec in self:
            # IVA en productos.producto es selection de strings ('0','8','16') → conviértelo
            rec.iva = float(rec.producto.iva or 0.0) if rec.producto else 0.0
            rec.ieps = float(rec.producto.ieps or 0.0) if rec.producto else 0.0
            # si no hay precio capturado aún, toma costo como default
            if rec.producto and not rec.precio_unitario:
                rec.precio_unitario = float(rec.producto.costo or 0.0)

    @api.depends('cantidad', 'precio_unitario')
    def _compute_subtotal(self):
        for rec in self:
            qty = rec.cantidad or 0.0
            price = rec.precio_unitario or 0.0
            rec.subtotal = qty * price

    @api.depends('subtotal', 'iva', 'ieps')
    def _compute_total(self):
        for rec in self:
            factor = 1.0 + (rec.iva or 0.0)/100.0 + (rec.ieps or 0.0)/100.0
            rec.total = (rec.subtotal or 0.0) * factor
