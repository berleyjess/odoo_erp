from odoo import models, fields, api
from datetime import date

class TransientEdocta(models.TransientModel):
    _name = 'transient.edocta'
    _description = 'Estado de Cuenta Transitorio'

    lines = fields.One2many('tmpline', 'edocta_id', string="Líneas")
    contrato_id = fields.Many2one('solcreditos.solcredito', string="Crédito")
    desde = fields.Date(string='Desde', default=fields.Date.today)
    hasta = fields.Date(string='Hasta', default=fields.Date.today)

    def _generar(self):
        self.ensure_one()
        self.lines.unlink()

        # Buscar transacciones con filtro de fechas
        cxcs = self.env['transacciones.transaccion'].search([
            ('contrato_id', '=', self.contrato_id.id),
            ('fecha', '>=', self.desde),
            ('fecha', '<=', self.hasta),
        ], order='fecha asc')  # Ordenar por fecha

        lineas = []
        balance = 0.0

        for linea in cxcs:
            balance += linea.saldo
            lineas.append((0, 0, {
                'edocta_id': self.id,
                'fecha': linea.fecha,
                'referencia': linea.referencia or '',
                'concepto': linea.producto_id.name if linea.producto_id else '',
                'cantidad': linea.cantidad,
                'precio': linea.precio,
                'iva': linea.iva_ammount,
                'ieps': linea.ieps_ammount,
                'importe': linea.importe,
                'cargo': linea.importe if linea.importe > 0 else 0.0,
                'abono': abs(linea.importe) if linea.importe < 0 else 0.0,
                'balance': balance,
            }))

        # Escribir las líneas
        self.write({'lines': lineas})
        return self._show_results()
    
    def _show_results(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Simulación de Estado de Cuenta',
            'res_model': self._name,  # ✅ CORREGIDO: usar self._name
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
            'views': [(False, 'form')]
        }