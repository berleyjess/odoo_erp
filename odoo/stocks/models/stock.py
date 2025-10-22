#stocks/models/stock.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class StockSucursalProducto(models.Model):
    _name = "stock.sucursal.producto"
    _description = "Existencias por Sucursal y Producto"
    _order = "sucursal_id, producto_id"

    sucursal_id = fields.Many2one("sucursales.sucursal", string="Sucursal", required=True, ondelete="cascade", index=True)
    producto_id = fields.Many2one("productos.producto", string="Producto", required=True, ondelete="restrict", index=True)
    cantidad = fields.Float("Cantidad", default=0.0, digits=(16, 4))

    _sql_constraints = [
        ("uniq_sucursal_producto", "unique(sucursal_id, producto_id)",
         "Ya existe un registro de stock para esa sucursal y producto.")
    ]

    @api.constrains("cantidad")
    def _check_cantidad(self):
        for rec in self:
            if rec.cantidad < 0:
                raise ValidationError(_("La cantidad no puede ser negativa."))

    @api.model
    def _get_or_create(self, sucursal, producto):
        rec = self.search([
            ("sucursal_id", "=", sucursal.id),
            ("producto_id", "=", producto.id)
        ], limit=1)
        if not rec:
            rec = self.create({
                "sucursal_id": sucursal.id,
                "producto_id": producto.id,
                "cantidad": 0.0,
            })
        return rec

    @api.model
    def add_stock(self, sucursal, producto, qty):
        """Incrementa stock con UPSERT atómico."""
        if not qty:
            return
        self.env.cr.execute("""
            INSERT INTO stock_sucursal_producto (sucursal_id, producto_id, cantidad)
            VALUES (%s, %s, %s)
            ON CONFLICT (sucursal_id, producto_id)
            DO UPDATE SET cantidad = stock_sucursal_producto.cantidad + EXCLUDED.cantidad
            RETURNING id
        """, (sucursal.id, producto.id, float(qty)))
        rid = self.env.cr.fetchone()[0]
        return self.browse(rid)

    @api.model
    def remove_stock(self, sucursal, producto, qty):
        """Decrementa stock de forma atómica; valida no-negativos."""
        if not qty:
            return
        self.env.cr.execute("""
            UPDATE stock_sucursal_producto
               SET cantidad = cantidad - %s
             WHERE sucursal_id = %s
               AND producto_id = %s
               AND cantidad >= %s
         RETURNING id, cantidad
        """, (float(qty), sucursal.id, producto.id, float(qty)))
        row = self.env.cr.fetchone()
        if not row:
            # Asegura existencia para el mensaje y muestra disponible real
            rec = self.search([("sucursal_id","=",sucursal.id),("producto_id","=",producto.id)], limit=1)
            disp = rec.cantidad if rec else 0.0
            raise ValidationError(_(
                "Stock insuficiente de %(prod)s en %(suc)s. Disponible: %(disp).4f, requerido: %(req).4f",
            ) % {
                "prod": producto.display_name,
                "suc": sucursal.display_name,
                "disp": disp,
                "req": qty,
            })
        return self.browse(row[0])

    @api.model
    def get_available(self, sucursal, producto):
        self.env.cr.execute("""
            SELECT cantidad FROM stock_sucursal_producto
             WHERE sucursal_id=%s AND producto_id=%s
        """, (sucursal.id, producto.id))
        row = self.env.cr.fetchone()
        return float(row[0]) if row else 0.0