from odoo import models, fields, api

class limiteinsumo(models.Model):
    _name = 'limiteinsumos.limiteinsumo'
    _description = 'Límite de insumos por contrato'

    limite = fields.Float(string="Unidad/Hectárea", required=True)
    producto = fields.Many2one('productos.producto', string="Producto", required=True)