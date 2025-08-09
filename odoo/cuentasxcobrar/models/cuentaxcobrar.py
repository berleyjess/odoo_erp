# cuentasxcobrar/models/cuentaxcobrar.py
from odoo import models, fields
from datetime import date

class CuentaXCobrar(models.Model):
    _name = 'cuentasxcobrar.cuentaxcobrar'
    _description = 'Línea de estado de cuenta'

    fecha = fields.Date(default=lambda self: date.today())
    referencia = fields.Char(string="Referencia")
    concepto = fields.Char(string="Concepto")

    # Mantén esto sin dependencias hacia otros módulos
    cantidad = fields.Float(string="Cantidad")
    precio   = fields.Float(string="Precio")
    importe  = fields.Float(string="Importe")
    ieps     = fields.Float(string="IEPS")
    iva      = fields.Float(string="IVA")

    cargo = fields.Float(string="Cargo")
    abono = fields.Float(string="Abono")
    saldo = fields.Float(string="Saldo")
