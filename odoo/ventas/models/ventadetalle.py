from odoo import models, fields, api

class ventadetalle(models.Model):
    _name='ventadetalle'
    _description = 'Detalle de la Venta de los artículos'

    ventaf = fields.Many2one('venta', string = "Venta", ondelete='cascade')
    producto = fields.Many2one('producto', string="Artículo", required = True)
    cantidad = fields.Float(string="Cantidad", required = True, default=0.0)
    precio = fields.Float(string = "Precio", required = True, default=0.0)
    importeb = fields.Float(compute='_calcimporte', string="Importe")
    importe = fields.Float(compute='_calcimporte',string="Importe")
    iva = fields.Float(string="iva", readonly=True)
    ieps = fields.Float(string="ieps", readonly=True)
    retiros = fields.Float(string="Retiros")
    devoluciones = fields.Float(string="Devoluciones")

    @api.onchange('producto')
    def _updateprice(self):
        for record in self:
            if record.producto:
                if record.ventaf.metododepago == 'PUE':
                    record.precio = record.producto.contado
                else:
                    record.precio = record.producto.credito

    @api.depends('precio', 'cantidad', 'producto')
    def _calcimporte(self):
        for field in self:
            self.importeb = self.cantidad * self.precio
            self.iva = self.producto.iva * self.importeb
            self.ieps = self.producto.ieps * self.importeb
            self.importe = self.importeb + self.iva +  self.ieps


    


