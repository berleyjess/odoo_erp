# -*- coding: utf-8 -*-
from odoo import models, fields, api

class compra(models.Model):
    _name = 'compras.compra'
    _description = "Modelo para compras"

    fecha = fields.Date(string="Fecha", default=fields.Date.context_today, required=True)
    proveedor = fields.Many2one('proveedores.proveedor', string='Proveedor', required=True)
    #detalle = fields.One2many('compras.detallecompra_ext', 'compra_id', string="Detalles de Compra")
    detalle = fields.One2Many('transacciones.transaccion', 'compra_id', string = "Detalles de Compra")

    codigo = fields.Char(
        string='Código', size=10, required=True, readonly=True, copy=False,
        default=lambda self: self._generate_code()
    )

    # Totales
    amount_subtotal = fields.Float(string='Subtotal', compute='_compute_totales', store=True)
    amount_iva = fields.Float(string='Total IVA', compute='_compute_totales', store=True)
    amount_ieps = fields.Float(string='Total IEPS', compute='_compute_totales', store=True)
    amount_total = fields.Float(string='Total general', compute='_compute_totales', store=True)

    @api.depends('detalle.subtotal', 'detalle.iva_amount', 'detalle.ieps_amount', 'detalle.total')
    def _compute_totales(self):
        for rec in self:
            lines = rec.detalle
            rec.amount_subtotal = sum(lines.mapped('subtotal'))
            rec.amount_iva = sum(lines.mapped('iva_amount'))
            rec.amount_ieps = sum(lines.mapped('ieps_amount'))
            rec.amount_total = sum(lines.mapped('total'))

    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_compra_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(6)}"
