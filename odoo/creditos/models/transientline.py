from odoo import models, fields

class transientline(models.TransientModel):
    _name = 'tmpline'

    edocta_id = fields.Many2one('transient.edocta', string = "Estado de Cuenta")
    fecha = fields.Date(string = "Fecha")
    referencia = fields.Char(string = "Referencia")
    concepto = fields.Char(string = "Concepto")
    cantidad = fields.Float(string = "Cantidad")
    precio = fields.Float(string = "Precio")
    iva = fields.Float(string= "Iva")
    ieps = fields.Float(string = "Ieps")
    importe = fields.Float(string = "Importe")
    cargo = fields.Float(string = "Cargo")
    abono = fields.Float(string = "Abono")
    balance = fields.Float(string = "Balance")
    saldo = fields.Float(string = "Saldo")
