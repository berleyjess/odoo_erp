from odoo import models, fields, api

class detallecompra_ext(models.Model):
    _name = 'compras.detallecompra_ext'
    _inherit = 'detallecompras.detallecompra'
    _description = 'Detalles/Conceptos de Compras Extendidos'

    compra_id = fields.Many2one('compras.compra', string="Compra", required=True, ondelete='cascade')