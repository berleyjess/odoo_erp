# models/transaccion_flags.py
from odoo import models, fields, api

class TxInvoiceLink(models.Model):
    _name = 'ventas.transaccion.invoice.link'
    _description = 'Ligas transacción ↔ factura (parciales)'
    _rec_name = 'display_name'

    transaccion_id = fields.Many2one('transacciones.transaccion', required=True, index=True, ondelete='cascade')
    move_id = fields.Many2one('account.move', required=True, index=True, ondelete='cascade')
    qty = fields.Float(default=0.0, string="Cantidad facturada")
    state = fields.Selection([
        ('open', 'Abierta'), 
        ('canceled', 'Cancelada')
    ], default='open', index=True)
    
    display_name = fields.Char(compute='_compute_display_name', store=True)
    
    @api.depends('transaccion_id', 'move_id', 'qty')
    def _compute_display_name(self):
        for r in self:
            r.display_name = f"{r.transaccion_id.display_name} → {r.move_id.name} ({r.qty:.2f})"

    _sql_constraints = [
        ('uniq_tx_per_move', 'unique(transaccion_id, move_id)',
         'La transacción ya está ligada a esta factura contable.'),
    ]


class Transaccion(models.Model):
    _inherit = 'transacciones.transaccion'

    link_ids = fields.One2many('ventas.transaccion.invoice.link', 'transaccion_id', string='Facturas ligadas')
    qty_invoiced = fields.Float(compute='_compute_inv_stats', store=True, string="Cantidad facturada")
    qty_available = fields.Float(compute='_compute_inv_stats', store=True, string="Cantidad disponible")
    
    invoice_status = fields.Selection([
        ('none', 'No facturada'),
        ('partial', 'Parcialmente facturada'),
        ('full', 'Facturada'),
        ('canceled', 'Cancelada'),
    ], compute='_compute_inv_stats', store=True, default='none', string="Estado de facturación")

    @api.depends('cantidad', 'link_ids.qty', 'link_ids.state')
    def _compute_inv_stats(self):
        EPS = 1e-6
        for r in self:
            # Solo suma links activos (no cancelados)
            q = sum(l.qty for l in r.link_ids.filtered(lambda x: x.state != 'canceled')) or 0.0
            r.qty_invoiced = q
            total = r.cantidad or 0.0
            r.qty_available = max(0, total - q)
            
            if q <= EPS:
                r.invoice_status = 'none'
            elif q + EPS >= total:
                r.invoice_status = 'full'
            else:
                r.invoice_status = 'partial'
    
    def _recompute_invoice_status(self):
        """Método auxiliar para forzar recálculo"""
        self._compute_inv_stats()


class Venta(models.Model):
    _inherit = 'ventas.venta'

    invoice_status2 = fields.Selection([
        ('none', 'No facturada'),
        ('partial', 'Parcial'),
        ('full', 'Facturada'),
        ('canceled', 'Cancelada'),
    ], compute='_compute_agg_status', store=True, default='none', string="Estado facturación")

    @api.depends('detalle.invoice_status')
    def _compute_agg_status(self):
        for v in self:
            if not v.detalle:
                v.invoice_status2 = 'none'
                continue
                
            states = set(v.detalle.mapped('invoice_status'))
            
            if states == {'none'}:
                v.invoice_status2 = 'none'
            elif states == {'full'}:
                v.invoice_status2 = 'full'
            elif 'partial' in states or ('full' in states and 'none' in states):
                v.invoice_status2 = 'partial'
            elif 'canceled' in states and len(states) == 1:
                v.invoice_status2 = 'canceled'
            else:
                v.invoice_status2 = 'partial'
