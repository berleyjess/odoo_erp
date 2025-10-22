from odoo import models, fields, api
from odoo.exceptions import ValidationError

class pagosdetail(models.Model):
    _name = 'pagosdetail.pagodetail'
    _description = 'Detalle de Pagos'

    pago_id = fields.Many2one('pagos.pago', string='Pago relacionado', ondelete='cascade', store = True)
    venta_id = fields.Many2one('ventas.venta', string='Venta', ondelete='set null', store = True)
    cargo_id = fields.Many2one('cargosdetail.cargodetail', string='Cargo', ondelete='cascade', store = True)
    monto = fields.Float(string='Monto', store = True)
    referencia = fields.Char(string="Referencia", compute='_compute_referencia', readonly=True)
    saldo = fields.Float(string="Saldo", readonly = True, compute='_compute_referencia')
    resto = fields.Float(string='Resto', compute='_compute_resto')

    @api.depends('venta_id', 'cargo_id')
    def _compute_referencia(self):
        for record in self:
            if record.venta_id or record.cargo_id:
                record.referencia = f"Pago a Venta #{record.venta_id.id}" if record.venta_id else (f"Pago a Cargo #{record.cargo_id.id}" if record.cargo_id else "")
                record.saldo = record.venta_id.saldo if record.venta_id else record.cargo_id.saldo
            
    def app_pago(self):
        for r in self:
            if r.venta_id:
                r.venta_id.pagos += r.pagos
            if r.cargo_id:
                r.cargo_id.pagos += r.pagos

    def discard_pago(self):
        for r in self:
            if r.venta_id:
                r.venta_id.pagos -= r.pagos
            if r.cargo_id:
                r.cargo_id.pagos -= r.pagos

    def _compute_resto(self):
        for record in self:
            if record.venta_id or record.cargo_id:
                record.resto = record.saldo - record.monto

    @api.constrains('monto')
    def _check_monto(self):
        for record in self:
            if record.venta_id or record.cargo_id:
                if record.monto > record.saldo:
                    raise ValidationError("El monto del pago no puede exceder el saldo del cargo relacionado.")
            #if record.monto <= 0:
            #    raise ValidationError("El monto del pago debe ser mayor a $0.")