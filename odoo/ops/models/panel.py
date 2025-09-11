# ops/models/panel.py
from odoo import models, fields, _, api

class OpsPanel(models.Model):
    _name = 'ops.panel'
    _description = 'Panel de Operaciones'

    name = fields.Char(default="Panel", readonly=True)
    # (opcional) contadores que quieras enseñar en los botones:
    ventas_hoy = fields.Integer(compute='_compute_counts', string="Ventas hoy")
    clientes_total = fields.Integer(compute='_compute_counts', string="Clientes")
    def _compute_counts(self):
        Sale = self.env['ventas.venta'].sudo()
        Client = self.env['clientes.cliente'].sudo()
        today = fields.Date.context_today(self)
        for r in self:
            r.ventas_hoy = Sale.search_count([('fecha', '=', today)])
            r.clientes_total = Client.search_count([])

    # Botones que necesitan contexto especial (abrir en modo edición, etc.)
    def action_clientes_nuevo(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nuevo cliente'),
            'res_model': 'clientes.cliente',
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},  # abre directo en edición
        }
    def action_ventas_listado(self):
        # si ya tienes la acción XML ID, devuélvela mejor con env.ref(...).read()[0]
        return self.env.ref('ventas.action_ventas').read()[0]
    def action_ventas_nueva(self):
        return self.env.ref('ventas.action_ventas_new').read()[0]
    def action_clientes_listado(self):
        return self.env.ref('clientes.action_clientes').read()[0]
    def action_stock(self):
        return self.env.ref('stocks.action_stock_sucursal_producto_list').read()[0]

    @api.model
    def action_open_singleton(self):
        rec = self.sudo().search([], limit=1) or self.sudo().create({})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ops.panel',
            'view_mode': 'form',
            'res_id': rec.id,
            'target': 'current',
        }