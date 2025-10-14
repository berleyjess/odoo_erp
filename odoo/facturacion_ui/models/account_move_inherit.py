#facturacion_ui/models/account_move_inherit.py
from odoo import models, fields, api 
class AccountMove(models.Model):
    _inherit = 'account.move'

    # Override: al cancelar la factura contable, marca como 'canceled' los links
    # ventas.transaccion.invoice.link asociados (state='open') y recomputa el estado
    # de facturación de las transacciones afectadas. Llama a super() primero.
    def button_cancel(self):
        """Si se cancela la factura, marca enlaces como cancelados"""
        res = super().button_cancel()
        
        Link = self.env['ventas.transaccion.invoice.link']
        links = Link.search([
            ('move_id', 'in', self.ids), 
            ('state', '=', 'open')
        ])
        
        if links:
            links.write({'state': 'canceled'})
            # Recalcular estatus de las transacciones afectadas
            transacciones = links.mapped('transaccion_id')
            if transacciones:
                transacciones._recompute_invoice_status()
        
        return res
    
    # Override: al regresar la factura a borrador, reactiva links previamente
    # cancelados (state='open') y recomputa el estado de facturación de las
    # transacciones afectadas. Llama a super() primero.
    def button_draft(self):
        """Si se pasa a borrador, reactiva los links"""
        res = super().button_draft()
        
        Link = self.env['ventas.transaccion.invoice.link']
        links = Link.search([
            ('move_id', 'in', self.ids), 
            ('state', '=', 'canceled')
        ])
        
        if links:
            links.write({'state': 'open'})
            transacciones = links.mapped('transaccion_id')
            if transacciones:
                transacciones._recompute_invoice_status()
        
        return res