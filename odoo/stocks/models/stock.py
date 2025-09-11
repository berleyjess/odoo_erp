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
        """Incrementa stock (crea línea si no existe)."""
        if not qty:
            return
        line = self._get_or_create(sucursal, producto)
        line.cantidad = (line.cantidad or 0.0) + float(qty)
        return line

    @api.model
    def remove_stock(self, sucursal, producto, qty):
        """Decrementa stock (valida no-negativos)."""
        if not qty:
            return
        line = self._get_or_create(sucursal, producto)
        nueva = (line.cantidad or 0.0) - float(qty)
        if nueva < 0:
            raise ValidationError(_(
                "Stock insuficiente de %(prod)s en %(suc)s. Disponible: %(disp).4f, requerido: %(req).4f",
            ) % {
                "prod": producto.display_name,
                "suc": sucursal.display_name,
                "disp": line.cantidad or 0.0,
                "req": qty,
            })
        line.cantidad = nueva
        return line

    @api.model
    def get_available(self, sucursal, producto):
        """Devuelve cantidad disponible en sucursal+producto (crea con 0 si no existe)."""
        return self._get_or_create(sucursal, producto).cantidad or 0.0