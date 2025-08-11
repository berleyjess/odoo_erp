# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class StockSucursalProducto(models.Model):
    _name = "stock.sucursal.producto"
    _description = "Existencias por Sucursal y Producto"
    _order = "sucursal_id, producto_id"

    sucursal_id = fields.Many2one("sucursales.sucursal", string="Sucursal", required=True, ondelete="cascade")
    producto_id = fields.Many2one("productos.producto", string="Producto", required=True, ondelete="restrict")
    cantidad = fields.Float("Cantidad", default=0.0, digits=(16, 4))

    _sql_constraints = [
        ("uniq_sucursal_producto", "unique(sucursal_id, producto_id)",
         "Ya existe un registro de stock para esa sucursal y producto.")
    ]

    @api.constrains("cantidad")
    def _check_cantidad(self):
        for rec in self:
            if rec.cantidad < 0:
                raise ValidationError("La cantidad no puede ser negativa.")

    @api.model
    def _get_or_create(self, sucursal, producto):
        """Obtiene o crea la línea de stock para sucursal+producto."""
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
        """Incrementa stock (crea línea si no existe)."""
        if not qty:
            return
        line = self._get_or_create(sucursal, producto)
        line.cantidad = (line.cantidad or 0.0) + float(qty)
        return line
