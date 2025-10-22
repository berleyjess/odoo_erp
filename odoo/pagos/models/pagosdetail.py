from odoo import models, fields, api
from odoo.exceptions import ValidationError

class pagosdetail(models.Model):
    _name = 'pagos.pagodetail'
    _description = 'Detalle de Pagos'

    pago_id = fields.Many2one('pagos.pago', string='Pago relacionado', ondelete='cascade', store = True)
    venta_id = fields.Many2one('ventas.venta', string='Venta', ondelete='set null', store = True)
    cargo_id = fields.Many2one('cargosdetail.cargodetail', string='Cargo', ondelete='cascade', store = True)
    monto = fields.Float(string='Pago', store = True)
    referencia = fields.Char(string="Referencia", compute='_compute_referencia', readonly=True)
    descripcion = fields.Char(string="Descripción", compute='_compute_referencia', readonly=True)
    saldo = fields.Float(string="Saldo", readonly = True, compute='_compute_referencia')
    resto = fields.Float(string='Resto', compute='_compute_resto', readonly=True)
    pagostatus = fields.Selection(related='pago_id.status', string="Estado del Pago", readonly=True)

    @api.depends('venta_id', 'cargo_id')
    def _compute_referencia(self):
        for record in self:
            if record.venta_id or record.cargo_id:
                record.referencia = f"{record.venta_id.folio}" if record.venta_id else (f"{record.cargo_id.folio}" if record.cargo_id else "")
                record.descripcion = f"{record.venta_id.descripcion}" if record.venta_id else (f"{record.cargo_id.descripcion}" if record.cargo_id else "")
                record.saldo = record.venta_id.saldo if record.venta_id else record.cargo_id.saldo
            
    def app_pago(self):
        for r in self:
            if r.venta_id and r.pagostatus == 'posted':
                r.venta_id.pagos += r.monto
            if r.cargo_id and r.pagostatus == 'posted':
                r.cargo_id.pagos += r.monto

    def discard_pago(self):
        for r in self:
            if r.venta_id and r.pagostatus == 'posted':
                r.venta_id.pagos -= r.monto
            if r.cargo_id and r.pagostatus == 'posted':
                r.cargo_id.pagos -= r.monto

    @api.depends('monto', 'cargo_id', 'venta_id')
    def _compute_resto(self):
        for record in self:
            if record.venta_id or record.cargo_id:
                record.resto = record.saldo - record.monto
                record.pago_id.compute_monto()

    """@api.constrains('venta_id', 'cargo_id')
    def _checkcargos(self):
        for record in self:
            if self.env['pagos.pagodetail'].search_count([('pago_id', '=', record.pago_id.id),('cargo_id', '=', record.cargo_id.id)]) > 1 or self.env['pagos.pagodetail'].search_count([('pago_id', '=', record.pago_id.id),('venta_id', '=', record.venta_id.id)]) > 1:
               raise ValidationError("El cargo seleccionado ya ha sido agregado a este pago. Por favor, seleccione otro cargo.")
    """        
    @api.constrains('monto')
    def _check_monto(self):
        for record in self:
            if record.venta_id or record.cargo_id:
                if record.monto > record.saldo:
                    raise ValidationError("El monto del pago no puede exceder el saldo del cargo relacionado.")
                record.pago_id.compute_monto()
            #if record.monto <= 0:
            #    raise ValidationError("El monto del pago debe ser mayor a $0.")
    
    @api.model
    def unlink(self):
        for record in self:
            pago = self.filtered(lambda r: r.pago_id).mapped('pago_id')
            if record.venta_id or record.cargo_id:
                record.discard_pago()
            result = super().unlink()
            pago.compute_monto()
        return result

    @api.constrains('tipoventa', 'cliente', 'credito')  # Agrega los campos que quieres bloquear
    def _check_modification_with_details(self):
        for record in self:
            if record.details and len(record.details) > 0:
                # Verifica si algún campo crítico ha cambiado
                if any(field in record._get_dirty_fields() for field in ['tipoventa', 'cliente', 'credito']):
                    raise ValidationError(_(
                        "No se pueden modificar los datos del pago cuando ya existen detalles agregados: "
                        "Elimine primero los detalles antes de realizar cambios."
                    ))
    def action_eliminar(self):
        for r in self:
            if r:
                r.unlink()