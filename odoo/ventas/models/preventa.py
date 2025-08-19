from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class Preventa(models.Model):
    _name = 'ventas.preventa'
    _inherit = 'ventas.venta'
    _description = 'Preventa (sin stock ni CxC)'

    # Redefinir One2many para separar DB de líneas
    #detalle = fields.One2many('ventas.detallepreventa_ext', 'preventa_id', string="Preventas")
    detalle = fields.One2many('transacciones.transaccion', 'preventa_id', string="Preventas")

    _sql_constraints = [
        ('preventa_codigo_uniq', 'unique(codigo)', 'El código de la preventa debe ser único.'),
    ]


    @api.model
    def create(self, vals):
        if not vals.get('codigo'):
            serie = 'XX'
            if vals.get('sucursal_id'):
                suc = self.env['sucursales.sucursal'].browse(vals['sucursal_id'])
                serie = (suc.serie or 'XX')
            seq = self.env['ir.sequence'].next_by_code('seq_preventa_code') or '/'
            num = (seq.split('/')[-1]).zfill(6)
            vals['codigo'] = f"{serie}-PV-{num}"
        rec = super().create(vals)
        return rec


    # Anular posteo CxC heredado
    def _post_to_statement_if_needed(self):
        return
    
    def action_manual_save(self):
        return True


    # ----- Conversión Preventa -> Venta -----
    def _check_stock_for_conversion(self):
        """Verifica stock suficiente en la sucursal antes de convertir a Venta."""
        Stock = self.env['stock.sucursal.producto']
        for p in self:
            prod_ids = p.detalle.mapped('producto').ids
            stocks = Stock.search([
                ('sucursal_id', '=', p.sucursal_id.id),
                ('producto_id', 'in', prod_ids),
            ])
            stock_map = {(s.producto_id.id): s for s in stocks}
            for line in p.detalle:
                sline = stock_map.get(line.producto_id.id)
                qty_avail = sline.cantidad if sline else 0.0
                if line.c_salida > qty_avail:
                    raise ValidationError(_(
                        "No hay stock suficiente para %s en %s. Requerido %.2f, disponible %.2f."
                    ) % (line.producto.display_name, p.sucursal_id.display_name, line.c_salida, qty_avail))
        return True

    def action_convert_to_venta(self):
        self.ensure_one()
        # 1) Verificar stock
        self._check_stock_for_conversion()

        # 2) Crear venta
        venta_vals = {
            'cliente': self.cliente.id,
            'contrato': self.contrato.id if self.contrato else False,
            'fecha': fields.Date.today(),
            'sucursal_id': self.sucursal_id.id,
            'metododepago': self.metododepago,
            'formadepago': self.formadepago,
            'solicita': self.solicita,
            'observaciones': self.observaciones,
        }
        venta = self.env['ventas.venta'].create(venta_vals)

        # 3) Copiar líneas (se reprecifican en create/write de venta si aplica)
        DetVenta = self.env['ventas.detalleventa_ext']
        for line in self.detalle:
            DetVenta.create({
                'venta_id': venta.id,
                'producto': line.producto_id.id,
                'cantidad': line.c_salida,
                'precio': line.precio,
            })

        # 4) Confirmar y descontar stock automáticamente (si no quieres automático, comenta esta línea)
        venta.action_confirm()

        # 5) Abrir la venta creada
        return {
            'type': 'ir.actions.act_window',
            'name': _('Venta'),
            'res_model': 'ventas.venta',
            'res_id': venta.id,
            'view_mode': 'form',
            'target': 'current',
        }
