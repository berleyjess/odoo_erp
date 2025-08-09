from odoo import models, fields, api

class detalleventa(models.Model):
    _name='detalleventas.detalleventa'
    _description = 'Detalle de la Venta de los artículos'

    producto = fields.Many2one('productos.producto', string="Artículo", required=True)
    cantidad = fields.Float(string="Cantidad", required=True, default=0.0)
    precio   = fields.Float(string="Precio", required=True, default=0.0)

    importeb = fields.Float(string="Importe base", compute='_compute_importes', store=True)
    importe  = fields.Float(string="Importe total", compute='_compute_importes', store=True)

    iva  = fields.Float(string="iva",  compute='_compute_importes', store=True)
    ieps = fields.Float(string="ieps", compute='_compute_importes', store=True)

    retiros      = fields.Float(string="Retiros")
    devoluciones = fields.Float(string="Devoluciones")

    @api.depends('cantidad', 'precio', 'producto', 'producto.iva', 'producto.ieps')
    def _compute_importes(self):
        for rec in self:
            qty   = float(rec.cantidad or 0.0)
            price = float(rec.precio or 0.0)
            base  = qty * price

            # Si tus productos guardan tasas como '0.16' (texto) o 0.16 (float),
            # esto lo vuelve número siempre.
            try:
                iva_rate = float(rec.producto.iva or 0.0)
            except Exception:
                iva_rate = 0.0
            try:
                ieps_rate = float(rec.producto.ieps or 0.0)
            except Exception:
                ieps_rate = 0.0

            rec.importeb = base
            rec.iva      = base * iva_rate
            rec.ieps     = base * ieps_rate
            rec.importe  = base + rec.iva + rec.ieps

