# models/account_move_inherit.py
from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'
#Si se cancela la factura contable, marca enlaces como cancelados
    def button_cancel(self):
        res = super().button_cancel()
        Link = self.env['ventas.transaccion.invoice.link']
        links = Link.search([('move_id','in', self.ids), ('state','=','open')])
        links.write({'state':'canceled'})
        # Recalcular estatus de las transacciones afectadas
        links.mapped('transaccion_id')._recompute_invoice_status()
        return res
