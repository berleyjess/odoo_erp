from odoo import models, fields, api
from datetime import date

class cuentaxcobrar(models.Model):
    _name = 'cuentasxcobrar.cuentaxcobrar'

    fecha = fields.Date(store = True, default = lambda self: date.today())
    referencia = fields.Char(string = "Referencia", store = True)
    concepto = fields.Char(string = "Concepto", store = True)

    #contrato_id = fields.Many2one('solcreditos.solcredito', string="Contrato", store = True)
    #venta_id = fields.Many2one('ventas.venta', string = "Venta", store = True)
    #cliente_id = fields.Many2one('clientes.cliente', string = "Cliente", store = True)
    detalle_id = fields.Many2one('detalleventas.detalleventa', string = "Detalle", store = True)
    #cargo_id = fields.Many2one('cargos.cargo', string ="Cargo", store = True)
    #pago_id = fields.Many2one('pagos.pago', string="Pago", store = True)

    cantidad = fields.Float(string = "Cantidad", store = True)
    precio = fields.Float(string="Precio", store = True)
    importe = fields.Float(string = "Importe", store = True)
    ieps = fields.Float(string="ieps", store = True)
    iva = fields.Float(string="iva", store = True)

    cargo = fields.Float(string = "Cargo", store = True)
    abono = fields.Float(string = "Abono", store = True)
    saldo = fields.Float(string = "Saldo", store = True)

                
