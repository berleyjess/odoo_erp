# -*- coding: utf-8 -*-
from odoo import models, fields, api

class compra(models.Model):
    _name = 'compras.compra'
    _description = "Modelo para compras"

    fecha = fields.Date(string="Fecha", default=fields.Date.context_today, required=True)
    proveedor = fields.Many2one('proveedores.proveedor', string='Proveedor', required=True)
    #detalle = fields.One2many('compras.detallecompra_ext', 'compra_id', string="Detalles de Compra")
    detalle = fields.One2many('transacciones.transaccion', 'compra_id', string = "Detalles de Compra")

    codigo = fields.Char(
        string='Código', size=10, required=True, readonly=True, copy=False,
        default=lambda self: self._generate_code()
    )

    # Totales
    amount_subtotal = fields.Float(string='Subtotal', compute='_compute_totales', store=True)
    amount_iva = fields.Float(string='Total IVA', compute='_compute_totales', store=True)
    amount_ieps = fields.Float(string='Total IEPS', compute='_compute_totales', store=True)
    amount_total = fields.Float(string='Total general', compute='_compute_totales', store=True)

    @api.depends('detalle.subtotal', 'detalle.iva_amount', 'detalle.ieps_amount', 'detalle.importe')
    def _compute_totales(self):
        for rec in self:
            lines = rec.detalle
            rec.amount_subtotal = sum(lines.mapped('subtotal'))
            rec.amount_iva = sum(lines.mapped('iva_amount'))
            rec.amount_ieps = sum(lines.mapped('ieps_amount'))
            rec.amount_total = sum(lines.mapped('importe'))

    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_compra_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(6)}"

    def action_open_edit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Editar compra',
            'res_model': 'compras.compra',
            'view_mode': 'form',
            'views': [(self.env.ref('compras.view_compras_form').id, 'form')],  # <- aquí
            'res_id': self.id,
            'target': 'current',
            'context': dict(self.env.context, form_view_initial_mode='edit'),
        }

    def action_save_button(self):
    
        """Botón 'Guardar': el cliente web guarda el formulario primero,
        luego llama a este método. Regresamos a la misma ficha en readonly."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Compra',
            'res_model': 'compras.compra',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'context': dict(self.env.context, form_view_initial_mode='readonly'),
        }
    
    def action_back_to_list(self):
        """Regresa al listado de compras."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Compras'),
            'res_model': 'compras.compra',
            'view_mode': 'list,form',
            'target': 'current',
        }
