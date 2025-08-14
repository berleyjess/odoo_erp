# -*- coding: utf-8 -*-
from odoo import models, fields, api

class DetalleCompra(models.Model):
    _name = 'compras.detallecompra_ext'
    _description = 'Detalle de Compra'

    compra_id = fields.Many2one('compras.compra', string='Compra', required=True, ondelete='cascade')
    producto = fields.Many2one('productos.producto', string='Producto', required=True)
    cantidad = fields.Float(string='Cantidad', default=0.0, required=True)
    precio_unitario = fields.Float(string='Precio unitario', default=0.0, required=True)

    # Importes calculados (no editables)
    subtotal = fields.Float(string='Subtotal', compute='_compute_importes', store=True)
    iva_amount = fields.Float(string='IVA', compute='_compute_importes', store=True)
    ieps_amount = fields.Float(string='IEPS', compute='_compute_importes', store=True)
    total = fields.Float(string='Total', compute='_compute_importes', store=True)

    # Para controlar lo ya aplicado a stock por línea (cuando la compra está confirmada)
    applied_qty = fields.Float(string='Cantidad aplicada a stock', default=0.0, readonly=True)

    # -------------------------------------------------------------------------
    # PRECIO POR DEFECTO = PRECIO DE CONTADO
    # -------------------------------------------------------------------------
    @api.onchange('producto')
    def _onchange_producto_set_precio_contado(self):
        """Al elegir producto, proponer precio de contado (editable por el usuario)."""
        if self.producto:
            self.precio_unitario = float(self.producto.contado or 0.0)

    @api.model
    def create(self, vals):
        # Si no mandan precio, usar contado del producto
        if not vals.get('precio_unitario') and vals.get('producto'):
            prod = self.env['productos.producto'].browse(vals['producto'])
            vals['precio_unitario'] = float(prod.contado or 0.0)

        rec = super().create(vals)
        compra = rec.compra_id
        if compra and compra.state == 'confirmed':
            rec._stock_add(compra.sucursal_id, rec.producto, rec.cantidad)
            rec.applied_qty = rec.cantidad
        return rec

    def write(self, vals):
        # Si cambian el producto y no mandan precio, poner contado del nuevo producto
        if 'producto' in vals and 'precio_unitario' not in vals:
            prod = self.env['productos.producto'].browse(vals['producto'])
            vals = dict(vals, precio_unitario=float(prod.contado or 0.0))

        # antes de escribir guardamos producto y qty aplicada
        before = {r.id: (r.producto.id, r.applied_qty) for r in self}
        res = super().write(vals)

        for rec in self:
            compra = rec.compra_id
            if not compra or compra.state != 'confirmed':
                continue
            old_prod_id, old_applied = before.get(rec.id, (rec.producto.id, rec.applied_qty))
            old_applied = float(old_applied or 0.0)

            if old_prod_id != rec.producto.id:
                # Revertir lo aplicado al producto viejo y aplicar todo al nuevo
                if old_applied:
                    self._stock_add(compra.sucursal_id, self.env['productos.producto'].browse(old_prod_id), -old_applied)
                if rec.cantidad:
                    self._stock_add(compra.sucursal_id, rec.producto, rec.cantidad)
                rec.applied_qty = rec.cantidad
            else:
                # Mismo producto: aplicar delta de cantidad
                delta = float(rec.cantidad or 0.0) - old_applied
                if delta:
                    self._stock_add(compra.sucursal_id, rec.producto, delta)
                    rec.applied_qty = old_applied + delta
        return res

    @api.depends('cantidad', 'precio_unitario', 'producto.iva', 'producto.ieps')
    def _compute_importes(self):
        for rec in self:
            qty = float(rec.cantidad or 0.0)
            price = float(rec.precio_unitario or 0.0)
            base = qty * price
            try:
                iva_rate = float(rec.producto.iva or 0.0) / 100.0
            except Exception:
                iva_rate = 0.0
            try:
                ieps_rate = float(rec.producto.ieps or 0.0) / 100.0
            except Exception:
                ieps_rate = 0.0
            rec.subtotal = base
            rec.iva_amount = base * iva_rate
            rec.ieps_amount = base * ieps_rate
            rec.total = base + rec.iva_amount + rec.ieps_amount

    # ---------------- Ajustes de stock (cuando la compra ya está confirmada) ----------------
    def _stock_add(self, sucursal, producto, qty):
        if not qty:
            return
        Stock = self.env['stock.sucursal.producto']
        if qty < 0 and hasattr(Stock, 'remove_stock'):
            Stock.remove_stock(sucursal, producto, abs(qty))
        else:
            Stock.add_stock(sucursal, producto, qty)

    def unlink(self):
        for rec in self:
            compra = rec.compra_id
            if compra and compra.state == 'confirmed' and rec.applied_qty:
                self._stock_add(compra.sucursal_id, rec.producto, -rec.applied_qty)
        return super().unlink()
