from odoo import models, fields, api

class pagosdetail(models.Model):
    _name = 'pagosdetail.pagodetail'
    _description = 'Detalle de Pagos'

    pago_id = fields.Many2one('pagos.pago', string='Pago relacionado', ondelete='cascade', store = True)
    venta_id = fields.Many2one('ventas.venta', string='Venta', ondelete='set null', store = True)
    cargo_id = fields.Many2one('cargos.cargo', string='Cargo', ondelete='set null')
    monto = fields.Float(string='Monto', required=True, store = True)
    referencia = fields.Float(string="Referencia", store = True)

    @api.depends('venta_id', 'cargo_id')
    def _compute_referencia(self):
        for record in self:
            record.referencia = f"Pago a Venta #{record.venta_id.id}" if record.venta_id else (f"Pago a Cargo #{record.cargo_id.id}" if record.cargo_id else "")

    def app_pago(self):
        for r in self:
            if r.venta_id:
                r.venta_id.saldo -= r.monto
            if r.cargo_id:
                r.cargo_id.saldo -= r.monto

    def discard_pago(self):
        for r in self:
            if r.venta_id:
                r.venta_id.saldo += r.monto
            if r.cargo_id:
                r.cargo_id.saldo += r.monto