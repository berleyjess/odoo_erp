from odoo import models, fields
from datetime import date

class transientmodel(models.TransientModel):
    _name = 'edocta'

    lines = fields.One2many('tmpline', 'edocta_id', string = "Lineas")
    contrato_id = fields.Many2one('solcreditos.solcredito', string = "Crédito")

    desde = fields.Date(string = 'Desde', default = date.today())
    hasta = fields.Date(string = 'Hasta', default = date.today())

    def _generar(self):
        self.ensure_one()
        self.lines.unlink()

        cxcs = self.env['cuentasxcobrar.cuentaxcobrar'].search([
            ('contrato_id', '=', self.contrato_id.id),
        ])

        lineas = []
        balance = 0.0

        for linea in cxcs:
            balance += linea.saldo
            lineas.append((0,0,{
                'edocta_id': self.contrato_id,
                'fecha': linea.fecha,
                'referencia': linea.referencia,
                'concepto': linea.concepto,
                'cantidad': linea.cantidad,
                'precio': linea.precio,
                'iva': linea.iva,
                'ieps': linea.ieps,
                'importe': linea.importe,
                'cargo': linea.cargo,
                'abono': linea.abono,
                'balance': balance,
            }
            ))
        balance+=self.contrato_id.intereses
        lineas.append((0,0,{
            'edocta_id': self.contrato_id,
            'fecha': fields.Date.today(),
            #'referencia': linea.referencia,
            'concepto': "Intereses",
            'cantidad': 1,
            'precio': self.contrato_id.intereses,
            'iva': 0.0,
            'ieps': 0.0,
            'importe': 0.0,
            'cargo': self.contrato_id.intereses,
            'abono': 0.0,
            'balance': balance,
        }))

        return self._show_results()
    
    def _show_results(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Simulación de Estado de Cuenta',
            'res_model': 'edocta',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,  # Añadir contexto
            'views': [(False, 'form')]  # Especificar la vista
        }