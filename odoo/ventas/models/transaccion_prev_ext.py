#ventas/models/transaccion_prev_ext.py
from odoo import models, fields, api

class transaccion_ext(models.Model):
    _inherit  = 'transacciones.transaccion'

    preventa_id = fields.Many2one('ventas.venta', string = "Venta")

    @api.onchange('venta_id')
    def _def_tipo(self):
        for i in self:
            i.tipo = 2

    @api.onchange('producto_id')
    def _mod_producto(self):
        for i in self:
            if i.producto_id:
                i.iva = i.producto_id.iva
                i.ieps = i.producto_id.ieps
                if i.tipo == 1:
                    i.precio = i.producto_id.costo
                elif i.tipo == 0:
                    i.precio = i.producto_id.contado if i.venta_id.metododepago == "PUE" else i.producto_id.credito