from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class pagos(models.Model):
    _name = 'pagos.pago'
    _description = 'Registro de pagos a ventas y cargos.'

    fecha = fields.Date(string = "Fecha de Pago", default=fields.Date.context_today, required=True, store = True)
    metodo = fields.Selection(string = "Método de Pago", selection=[
        ('0', 'Efectivo'),
        ('1', 'Tarjeta de Crédito/Débito'),
        ('2', 'Transferencia Electrónica'),
        ('3', 'Cheque'),
        ('4', 'Compensación')
    ], required=True, default='0', store = True)
    monto = fields.Float(string = "Monto total", required = True, default = 0.0, store = True, readonly = True)

    #banco = fields.Many2one('bancos.banco', string="Banco", required=True)
    folio = fields.Char(string="Folio", copy=False, index=True, default=lambda self: _('Nuevo'), store = True, readonly=True)
    status = fields.Selection(string="Estado", selection=[
        ('draft', 'Borrador'),
        ('posted', 'Publicado'),
        ('cancelled', 'Cancelado')
    ])
    details = fields.One2many('pagosdetail.pagodetail', 'pago_id', string='Detalles de Pago', store = True)

    observaciones = fields.Char(string ="Observaciones", store = True)

    cliente = fields.Many2one('clientes.cliente', string = "Cliente", ondelete='set null', store = True)
    credito = fields.Many2one('creditos.credito', string = "Crédito", ondelete='set null', store = True)
    tipoventa = fields.Selection(string="Tipo", selection=[
        ('0', 'Contado'),
        ('1', 'Crédito')
    ], store = True)
    
    @api.depends('status')
    def _compute_status(self):
        for record in self:
            if record.status == 'posted':
                record.folio = self.env['ir.sequence'].next_by_code('pagos.folio')
                for line in record.details:
                    line.app_pago()
            elif record.status == 'cancelled':
                for line in record.details:
                    line.discard_pago()

    @api.depends('details')
    def _compute_monto(self):
        for record in self:
            record.monto = sum(line.monto for line in record.details)

    @api.depends('venta_id', 'cargo_id')
    def _compute_referencia(self):
        for record in self:
            record.referencia = f"Pago a Venta #{record.venta_id.id}" if record.venta_id else (f"Pago a Cargo #{record.cargo_id.id}" if record.cargo_id else "")
            record.saldo = record.venta_id.saldo if record.venta_id else record.cargo_id

    @api.constrains('monto')
    def _check_monto(self):
        for record in self:
            if record.monto > record.saldo:
                raise ValidationError("El monto del pago no puede exceder el saldo del cargo relacionada.")

