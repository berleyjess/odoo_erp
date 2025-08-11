# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class Compra(models.Model):
    _inherit = "compras.compra"

    sucursal_id = fields.Many2one("sucursales.sucursal", string="Sucursal", required=True)
    state = fields.Selection([
        ("draft", "Borrador"),
        ("confirmed", "Confirmada"),
    ], string="Estado", default="draft")

    stock_aplicado = fields.Boolean(string="Stock aplicado", default=False, help="Evita aplicar dos veces.")

    def action_confirmar(self):
        """Confirma y aplica incrementos al stock por sucursal."""
        for compra in self:
            if compra.stock_aplicado:
                raise UserError(_("Esta compra ya aplicó al stock."))

            if not compra.detalle:
                raise UserError(_("La compra no tiene líneas de detalle."))

            for line in compra.detalle:
                producto = getattr(line, "producto", False)
                qty = getattr(line, "cantidad", 0.0)
                if not producto or not qty:
                    continue
                self.env["stock.sucursal.producto"].add_stock(compra.sucursal_id, producto, qty)

            compra.write({
                "state": "confirmed",
                "stock_aplicado": True,
            })
        return True
