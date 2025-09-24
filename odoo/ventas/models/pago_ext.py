from odoo import models, fields, api
from odoo.exceptions import ValidationError

class pago_ext(models.Model):
    _inherit = 'pagos.pago'

    venta_id = fields.Many2one(
        'ventas.venta',
        string='Venta relacionada',
        ondelete='set null'
    )

    saldoventa = fields.Float(
        string='Saldo de la Venta', relate = 'venta_id.saldo', readonly = True, store = True)
    
    @api.constrains('monto')
    def _check_monto(self):
        for record in self:
            if record.venta_id and record.monto > record.saldoventa:
                raise ValidationError("El monto del pago no puede exceder el saldo de la venta relacionada.")
