# models/transaccion_flags.py
#me sirve para saber que transacciones,ventas,intereses o cargos ya fueron facturadas y cuales no

from odoo import models, fields, api

class TxInvoiceLink(models.Model):
    _name = 'ventas.transaccion.invoice.link'
    _description = 'Ligas transacción ↔ factura (parciales)'
    _rec_name = 'display_name'

    transaccion_id = fields.Many2one('transacciones.transaccion', required=True, index=True, ondelete='cascade')
    move_id        = fields.Many2one('account.move', required=True, index=True, ondelete='cascade')
    qty            = fields.Float(default=0.0)  # cantidad facturada de esa transacción en ese move
    state          = fields.Selection([('open', 'Abierta'), ('canceled', 'Cancelada')], default='open', index=True)

    _sql_constraints = [
        # una transacción debe aparecer a lo más una vez por move
        ('uniq_tx_per_move', 'unique(transaccion_id, move_id)',
         'La transacción ya está ligada a esta factura contable.'),
    ]


class Transaccion(models.Model):
    _inherit = 'transacciones.transaccion'

    link_ids = fields.One2many('ventas.transaccion.invoice.link', 'transaccion_id', string='Facturas ligadas')

    qty_invoiced = fields.Float(compute='_compute_inv_stats', store=True)
    invoice_status = fields.Selection([
        ('none', 'No facturada'),
        ('partial', 'Parcialmente facturada'),
        ('full', 'Facturada'),
        ('canceled', 'Cancelada'),
    ], compute='_compute_inv_stats', store=True, default='none')

    @api.depends('cantidad', 'link_ids.qty', 'link_ids.state')
    def _compute_inv_stats(self):
        EPS = 1e-6
        for r in self:
            q = sum(l.qty for l in r.link_ids if l.state != 'canceled') or 0.0
            r.qty_invoiced = q
            total = r.cantidad or 0.0
            if q <= EPS:
                r.invoice_status = 'none'
            elif q + EPS < total:
                r.invoice_status = 'partial'
            else:
                r.invoice_status = 'full'


class Venta(models.Model):
    _inherit = 'ventas.venta'

    invoice_status2 = fields.Selection([
        ('none', 'No facturada'),
        ('partial', 'Parcial'),
        ('full', 'Facturada'),
        ('canceled', 'Cancelada'),
    ], compute='_compute_agg_status', store=True, default='none')

    @api.depends('detalle.invoice_status')
    def _compute_agg_status(self):
        for v in self:
            states = set(v.detalle.mapped('invoice_status'))
            if not states or states == {'none'}:
                v.invoice_status2 = 'none'
            elif 'partial' in states or ('full' in states and 'none' in states):
                v.invoice_status2 = 'partial'
            elif states == {'full'}:
                v.invoice_status2 = 'full'
            else:
                v.invoice_status2 = 'none'
