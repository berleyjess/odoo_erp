#ventas/models/transaccion_ext.py
from odoo import models, fields, api

class transaccion_ext(models.Model):
    _inherit  = 'transacciones.transaccion'

    venta_id = fields.Many2one('ventas.venta', string = "Venta")
    contrato_id = fields.Many2one('creditos.credito', string = "Contrato")
    cliente_id = fields.Many2one('clientes.cliente', string = "Cliente")

    @api.onchange('venta_id')
    def _def_tipo(self):
        for i in self:
            i.tipo = '1'

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

    @api.model
    def create(self, vals):
        # Solo procesar si venta_id está presente
        if vals.get('venta_id'):
            venta_obj = self.env['ventas.venta']
            venta = venta_obj.browse(vals['venta_id'])
            
            if venta.metododepago == 'PPD' and venta.contrato:
                vals['contrato_id'] = venta.contrato.id
            if venta.cliente:
                vals['cliente_id'] = venta.cliente.id
        
        return super().create(vals)