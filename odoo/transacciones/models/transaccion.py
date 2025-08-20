from odoo import models, fields, api
from datetime import date

class transaccion(models.Model):
    _name = 'transacciones.transaccion'
    _description = 'Detalles/Conceptos de Compra/Venta/Traspasos/Devoluciones'

    fecha = fields.Date(string = "Fecha", store = True, default = date.today())

    sucursal_id = fields.Many2one('sucursales.sucursal', string = "Origen")
    sucursal_d_id = fields.Many2one('sucursales.sucursal', string = "Destino")
    producto_id = fields.Many2one('productos.producto', string = "Producto", store = True, required = True)
    referencia = fields.Char(string = "Referencia", store = True)
    cantidad = fields.Float(string ="Cantidad", default = 0.0)
    precio = fields.Float(string  = "Precio", store = True, required = True, default = 0.0)
    iva = fields.Float(string = "Iva %", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    ieps = fields.Float(string = "Ieps %", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    iva_amount = fields.Float(string = "Iva", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    ieps_amount = fields.Float(string = "ieps", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    subtotal = fields.Float(string = "Subtotal", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    importe = fields.Float(string = "Importe", store = True, readonly = True, default = 0.0, compute = '_calc_montos')
    stock = fields.Selection(string = "Tipo", store = True, readonly = True, default = '0', selection = [
        ('0', "Sin efecto"),
        ('1', "Entrada"),
        ('2', "Salida"),
    ])
    tipo = fields.Selection(string ="Tipo de Transacción", store = True,
                            selection = [
                                ('0', "Compra"), # Entrada - Provisión de Factura
                                ('1', "Venta"), # Salida - Factura de Cliente
                                ('2', "Recepción"), # Entrada - Traspado de Sucursal
                                ('3', "Envío"), # Salida - Traspaso a Sucursal
                                ('4', "Producción"), # Entrada - Generación de Producto
                                ('5', "Costo"), # Salida - Costo de Producción
                                ('6', "Dev de Cliente"), # Entrada - NC a Cliente
                                ('7', "Dev a Proveedor"), # Salida - NC de Proveedor
                                ('8', "Excedente"), # Entrada - Excedente de Inventario
                                ('9', "Pérdida"), # Salida - Pérdida de Inventario
                                ('10', "Preventa") # No genera Movimiento de Stock
                            ])

    @api.depends('producto_id', 'cantidad', 'precio')
    def _calc_montos(self):
        for i in self:
            if i.producto_id:
                i.subtotal = i.cantidad * i.precio
                i.iva_amount = i.iva * i.importe
                i.ieps_amount = i.ieps * i.importe
                i.importe = i.subtotal + i.iva_amount + i.ieps_amount

    @api.depends('tipo')
    def _stock_tipo(self):
        for i in self:
            if i.tipo:
                if i.tipo == '10':
                    i.stock = '0'
                elif i.tipo % 2 == 0:
                    i.stock = '1'
                else:
                    i.stock = '2'
                    

