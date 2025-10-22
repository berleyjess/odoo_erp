from odoo import models, fields, api

import logging
_logger = logging.getLogger(__name__)
class cargarventas(models.TransientModel):
    _name = 'pagos.cargarventas'
    _description = 'Wizard para seleccionar venta'
    pago_id = fields.Many2one('pagos.pago', string='Pago')
    credito_id = fields.Many2one('creditos.credito', string='Crédito')
    cliente_id = fields.Many2one('clientes.cliente', string='Cliente')
    saldo = fields.Float(string="Saldo", related='venta_id.saldo', readonly=True)
    pagos = fields.Float(string="Pagos", related='venta_id.pagos', readonly=True)
    descripcion = fields.Char(string="Descripción", related='venta_id.observaciones', readonly=True)
    monto = fields.Float(string='Monto del Pago', default=0.0)
    venta_id = fields.Many2one(
        'ventas.venta', 
        string='Seleccionar Venta',
        domain=lambda self: self._get_venta_domain()
    )

    def _get_venta_domain(self):
        """Genera el dominio dinámicamente"""
        domain = [
            ('cliente', '=', self.cliente_id.id),
            ('saldo', '>', 0)
        ]
        
        if self.credito_id:
            domain.extend([
                '|',
                ('contrato', '=', self.credito_id.id),
                ('contrato', '=', False)
            ])
        
        return domain    


    @api.depends('venta_id')
    def _compute_venta_domain(self):
        for record in self:
            if record.credito_id:
                if record.venta_id in self.env['pagos.pagosdetail'].search([('pago_id', '=', record.pago_id.id), ('venta_id', '!=', False)]).mapped('venta_id'):
                    raise ValueError("La venta seleccionada ya ha sido agregada a este pago. Por favor, seleccione otra venta.")

    @api.depends('monto')
    def _compute_monto(self):
        for record in self:
            if record.monto <= 0:
                raise ValueError("El monto a pagar no puede ser $0")
            
            if record.saldo < record.monto:
                raise ValueError("El monto a pagar no puede ser mayor al saldo de la venta seleccionada.")

    def action_seleccionar_venta(self):
        """Selecciona la venta y cierra el wizard"""
        #self.pago_id.venta_id = self.venta_id.id
        _logger.info(f"*/*/*/*/*/ La venta que seleccionaste: {self.venta_id} Aplicar al pago {self.pago_id}/*/*/*/")
        try:
            #pagodetail_vals = {'pago_id': self.pago_id.id, 'cargo_id': self.cargo_id.id, 'monto': 0, }
            #self.pago_id.write({'details': [(0, 0, pagodetail_vals)]})
            self.pago_id.write({
                'details': [(0, 0, {
                    'venta_id': self.venta_id.id,
                    'monto': self.monto,
                })]
            })
            #self.pago_id.generar_pagodetail(pagodetail_vals)
            #self.env['pagosdetail.pagodetail'].create(pagodetail_vals)
        except Exception as e:
            _logger.error(f"Error al agregar el cargo al pago: {e}")
            raise

        return {'type': 'ir.actions.act_window_close'}
    