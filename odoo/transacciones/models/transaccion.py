from odoo import models, fields, api
from datetime import date

class transaccion(models.Model):
    _name = 'transacciones.transaccion'
    _description = 'Detalles/Conceptos de Compra/Venta/Traspasos/Devoluciones'

    fecha = fields.Date(string = "Fecha", store = True, default = date.today())

    producto_id = fields.Many2one('productos.producto', string = "Producto", store = True, required = True)
    referencia = fields.Char(string = "Referencia", store = True)
    c_entrada = fields.Float(string = "Entrada", store = True, required = True, default = 0.0)
    c_salida = fields.Float(string = "Salida", store = True, required = True, default = 0.0)
    precio = fields.Float(string  = "Precio", store = True, required = True, default = 0.0)
    iva = fields.Float(string = "Iva %", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    ieps = fields.Float(string = "Ieps %", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    iva_amount = fields.Float(string = "Iva", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    ieps_amount = fields.Float(string = "ieps", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    subtotal = fields.Float(string = "Subtotal", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    importe = fields.Float(string = "Importe", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    tipo = fields.Selection(string ="Tipo de Transacción", store = True,
                            selection = [
                                ('0', "Compra"),
                                ('1', "Venta"),
                                ('2', "Envío"),
                                ('3', "Recepción"),
                                ('4', "Costo"),
                                ('5', "Producción"),
                            ])

    @api.onchange('producto_id')
    def _mod_producto(self):
        for i in self:
            if i.producto_id:
                i.iva = i.producto_id.iva
                i.ieps = i.producto_id.ieps
                i.precio = i.producto_id.costo

    @api.depends('producto_id', 'c_entrada', 'c_salida', 'precio')
    def _calc_montos(self):
        for i in self:
            if i.producto_id:
                i.subtotal = (i.c_entrada + i.c_salida) * i.precio
                i.iva_amount = i.iva * i.importe
                i.ieps_amount = i.ieps * i.importe
                i.importe = i.subtotal + i.iva_amount + i.ieps_amount
