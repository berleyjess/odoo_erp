from odoo import models, fields, api

import logging
_logger = logging.getLogger(__name__)
class cargarcargos(models.TransientModel):
    _name = 'pagos.cargarcargos'
    _description = 'Wizard para seleccionar cargo'
    pago_id = fields.Many2one('pagos.pago', string='Pago')
    credito_id = fields.Many2one('creditos.credito', string='Crédito')
    saldo = fields.Float(string="Saldo", related='cargo_id.saldo', readonly=True)
    pagos = fields.Float(string="Pagos", related='cargo_id.pagos', readonly=True)
    descripcion = fields.Char(string="Descripción", related='cargo_id.descripcion', readonly=True)

    monto = fields.Float(string='Monto del Pago', default=0.0)

    cargo_id = fields.Many2one(
        'cargosdetail.cargodetail', 
        string='Cargo',
        domain = """[
            ('credito_id', '=', credito_id),
            ('saldo', '>', 0)
        ]"""
    )

    @api.depends('cargo_id')
    def _compute_cargo_domain(self):
        for record in self:
            if record.credito_id:
                if record.cargo_id in self.env['pagos.pagosdetail'].search([('pago_id', '=', record.pago_id.id), ('cargo_id', '!=', False)]).mapped('cargo_id'):
                    raise ValueError("El cargo seleccionado ya ha sido agregado a este pago. Por favor, seleccione otro cargo.")

    @api.depends('monto')
    def _compute_monto(self):
        for record in self:
            if record.monto <= 0:
                raise ValueError("El monto a pagar no puede ser $0")
            
            if record.saldo < record.monto:
                raise ValueError("El monto a pagar no puede ser mayor al saldo del cargo seleccionado.")

    def action_seleccionar_cargo(self):
        """Selecciona el cargo y cierra el wizard"""
        #self.pago_id.cargo_id = self.cargo_id.id
        _logger.info(f"*/*/*/*/*/ El cargo que seleccionaste: {self.cargo_id} Aplicar al pago {self.pago_id}/*/*/*/")
        try:
            #pagodetail_vals = {'pago_id': self.pago_id.id, 'cargo_id': self.cargo_id.id, 'monto': 0, }
            #self.pago_id.write({'details': [(0, 0, pagodetail_vals)]})
            self.pago_id.write({
                'details': [(0, 0, {
                    'cargo_id': self.cargo_id.id,
                    'monto': self.monto,
                })]
            })
            #self.pago_id.generar_pagodetail(pagodetail_vals)
            #self.env['pagosdetail.pagodetail'].create(pagodetail_vals)
        except Exception as e:
            _logger.error(f"Error al agregar el cargo al pago: {e}")
            raise

        return {'type': 'ir.actions.act_window_close'}
    
