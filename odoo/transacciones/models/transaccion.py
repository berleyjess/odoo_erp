from odoo import models, fields, api
from datetime import date

class transaccion(models.Model):
    _name = 'transacciones.transaccion'
    _description = 'Detalles/Conceptos de Compra/Venta/Traspasos/Devoluciones'

    fecha = fields.Date(string = "Fecha", store = True, default = date.today())

    producto_id = fields.Many2one(string = "Producto", store = True, required = True)
    referencia = fields.Char(string = "Referencia", store = True, required = True)
    c_entrada = fields.Float(string = "Entrada", store = True, required = True, default = 0.0)
    c_salida = fields.Float(string = "Salida", store = True, required = True, default = 0.0)
    precio = fields.Float(string  = "Precio", store = True, required = True, default = 0.0)
    iva = fields.Float(string = "Iva %", store = True, readonly = True, default = 0.0)
    ieps = fields.Float(string = "Ieps %", store = True, readonly = True, default = 0.0)
    iva_ammount = fields.Float(string = "Iva", store = True, readonly = True, default = 0.0)
    ieps_ammount = fields.Float(string = "ieps", store = True, readonly = True, default = 0.0)
    subtotal = fields.Float(string = "Subtotal", store = True, readonly = True, default = 0.0)
    importe = fields.Float(string = "Importe", store = True, readonly = True, default = 0.0)
    tipo = fields.Selection(string ="Tipo de Transacción", required = True, store = True,
                            selection = [
                                ('0', "Compra"),
                                ('1', "Venta"),
                                ('2', "Envío"),
                                ('3', "Recepción"),
                                ('4', "Costo"),
                                ('5', "Producción"),
                            ])

    @api.depends('producto_id', 'c_entrada', 'c_salida', 'precio')
    def _calc_montos(self):
        for i in self:
            i.iva = i.producto_id
            i.ieps = i.producto_id
            i.subtotal = (i.c_entrada + i.c_salida) * i.precio
            i.iva_ammount = i.iva * i.importe
            i.ieps_ammoun = i.ieps * i.importe
            i.importe = i.subtotal + i.iva_ammount + i.ieps_ammount
