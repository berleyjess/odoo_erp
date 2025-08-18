from odoo import models, fields, api

class transaccion_ext(models.Model):
    _inherit = 'transacciones.transaccion'

    compra_id = fields.Many2one(
        'compras.compra',
        string = "Compra"
    )

@api.depends('compra_id')
def _define_tipo(self):
    self.tipo = 0 #Se establece el tipo de transaccion 0 = Compra


