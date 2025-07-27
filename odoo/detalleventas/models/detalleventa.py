from odoo import models, fields, api

class detalleventa(models.Model):
    _name='detalleventas.detalleventa'
    _description = 'Detalle de la Venta de los artículos'

    producto = fields.Many2one('productos.producto', string="Artículo", required = True)
    cantidad = fields.Float(string="Cantidad", required = True, default=0.0)
    precio = fields.Float(string = "Precio", required = True, default=0.0)
    importeb = fields.Float(compute='_calcimporte', string="Importe")
    importe = fields.Float(compute='_calcimporte',string="Importe")

    #Impuestos
    iva = fields.Float(string="iva", readonly=True)
    ieps = fields.Float(string="ieps", readonly=True)

    #Movimientos de Bodega
    retiros = fields.Float(string="Retiros")
    devoluciones = fields.Float(string="Devoluciones")

    @api.depends('precio', 'cantidad', 'producto')
    def _calcimporte(self):
        for field in self:
            self.importeb = self.cantidad * self.precio
            self.iva = self.producto.iva * self.importeb
            self.ieps = self.producto.ieps * self.importeb
            self.importe = self.importeb + self.iva +  self.ieps


    


