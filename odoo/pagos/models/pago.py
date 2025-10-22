from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)
class pagos(models.Model):
    _name = 'pagos.pago'
    _description = 'Registro de pagos a ventas y cargos.'
    _rec_name = 'folio'

    fecha = fields.Date(string = "Fecha de Pago", default=fields.Date.context_today, required=True, store = True)
    metodo = fields.Selection(string = "Método de Pago", selection=[
        ('0', 'Efectivo'),
        ('1', 'Tarjeta de Crédito/Débito'),
        ('2', 'Transferencia Electrónica'),
        ('3', 'Cheque'),
        ('4', 'Compensación')
    ], required=True, default='0', store = True)
    monto = fields.Float(string = "Monto total del pago", required = True, default = 0.0, store = True, readonly = True, compute="_compute_monto")

    banco = fields.Char(string="Banco", required=True)
    folio = fields.Char(string="Folio", copy=False, default="Borrador", compute='_compute_status', store = True, readonly=True)
    status = fields.Selection(string="Estado", selection=[
        ('draft', 'Borrador'),
        ('posted', 'Aplicado'),
        ('cancelled', 'Cancelado')
    ], default = 'draft', store = True, compute='_compute_status', readonly=True)

    details = fields.One2many('pagos.pagodetail', 'pago_id', string='Detalles de Pago', store = True)

    observaciones = fields.Char(string ="Observaciones", store = True)

    tipoventa = fields.Selection(string="Tipo", selection=[
        ('0', 'Contado'),
        ('1', 'Crédito')
    ], store = True)

    cliente = fields.Many2one('clientes.cliente', string = "Cliente", ondelete='set null', store = True)
    credito = fields.Many2one('creditos.credito', string = "Crédito", ondelete='set null', store = True, 
            domain="[('cliente', '=', cliente), ('dictamen','=','confirmed')]" if cliente else "[('id', '=', 0)]")

    @api.constrains('status')
    def _compute_status(self):
        for record in self:
            if record.status == 'posted':
                for line in record.details:
                    line.app_pago()
            elif record.status == 'cancelled':
                for line in record.details:
                    line.discard_pago()
    
    @api.depends('details')
    def compute_monto(self):
        for record in self:
            record.monto = sum(line.monto for line in record.details)
            for l in record.details:
                credito = l.venta_id.contrato if l.venta_id else (l.cargo_id.credito_id if l.cargo_id else None)
                cliente= l.venta_id.cliente if l.venta_id else (l.cargo_id.credito_id.cliente if l.cargo_id and l.cargo_id.credito_id else None)

                if credito and record.tipoventa == '0':
                    raise ValidationError("No se pueden agregar ventas de crédito a un pago de contado.")
                if cliente and record.cliente != cliente:
                    raise ValidationError("El cliente del detalle no coincide con el cliente del pago.")
                if record.credito and credito != record.credito:
                    raise ValidationError("El crédito del detalle no coincide con el crédito del pago.")


    def action_cargarventas(self):
        for record in self:
            if record.status != 'draft':
                raise ValidationError("Este pago no puede ser modificado porque ya ha sido procesado.")
            if record.tipoventa == '1' and not record.credito:
                raise ValidationError("Por favor, seleccione un crédito antes de cargar ventas.")
            if not record.cliente:
                raise ValidationError("Por favor, seleccione un cliente antes de cargar ventas.")
            
        return {
            'name': 'Seleccionar Venta',
            'type': 'ir.actions.act_window',
            'res_model': 'pagos.cargarventas',
            'view_mode': 'form',
            'view_id': self.env.ref('pagos.view_cargar_ventas_wizard_form').id,
            'target': 'new',
            'context': {
                'default_pago_id': self.id,
                'default_cliente_id': self.cliente.id,
                'default_credito_id': self.credito.id,
            }
        }  
    
    def action_cargarcargos(self):
        for record in self:
            if record.status != 'draft':
                raise ValidationError("Este pago no puede ser modificado porque ya ha sido procesado.")
            if record.tipoventa == '0':
                raise ValidationError("No hay cargos disponibles para transacciones de contado.")
            if not record.credito:
                raise ValidationError("Por favor, seleccione un crédito antes de cargar cargos.")
            if not record.cliente:
                raise ValidationError("Por favor, seleccione un cliente antes de cargar cargos.")
            
        return {
            'name': 'Seleccionar Cargo',
            'type': 'ir.actions.act_window',
            'res_model': 'pagos.cargarcargos',
            'view_mode': 'form',
            'view_id': self.env.ref('pagos.view_cargar_cargos_wizard_form').id,
            'target': 'new',
            'context': {
                'default_pago_id': self.id,
                'default_credito_id': self.credito.id,
            }
        }
    
    def action_aplicar_pago(self):
        for record in self:
            if not record.details or record.monto <= 0:
                raise ValidationError("El monto del pago no puede ser $0")
            if record.status == 'posted':
                raise ValidationError("El pago ya fue aplicado.")
            record.folio = self.env['ir.sequence'].next_by_code('pagos.folio')      
            record.status = 'posted'
        return True
    
    def action_cancelar_pago(self):
        for record in self:
            if record.status != 'posted':
                raise ValidationError("El pago no puede ser cancelado.")
            record.status = 'cancelled'
        return True
