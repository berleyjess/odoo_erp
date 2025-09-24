from odoo import models, fields, api

class pago_ext(models.Model):
    _inherit = 'pagos.pago'

    credito_id = fields.Many2one(
        'creditos.credito',
        string='Crédito relacionado',
        ondelete='set null'
    )

    venta_id = fields.Many2one(
        'ventas.venta',
        string='Venta relacionada',
        ondelete='set null'
    )

    cargo_id = fields.Many2one(
        'cargos.cargo',
        string='Cargo relacionado',
        ondelete='set null'
    )