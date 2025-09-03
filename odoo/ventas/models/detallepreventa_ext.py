#ventas/models/detallepreventa_ext.py
from odoo import models, fields, api

class detallepreventa_ext(models.Model):
    _name='ventas.detallepreventa_ext'
    _description = 'Detalle de la Preventa de artículos'
    _inherit = 'detalleventas.detalleventa'

    preventa_id = fields.Many2one('ventas.preventa', string="Preventa", ondelete='cascade')

    @api.onchange('producto', 'preventa_id.metododepago')
    def _updateprice(self):
        for record in self:
            if record.producto:
                metodo = record.preventa_id.metododepago or 'PPD'
                record.precio = record.producto.contado if metodo == 'PUE' else record.producto.credito
