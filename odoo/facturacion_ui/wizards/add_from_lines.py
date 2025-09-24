# wizards/add_from_lines.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class WizAddLines(models.TransientModel):
    _name = 'facturas.wiz.add.lines'
    _description = 'Agregar transacciones sueltas'

    factura_id = fields.Many2one('facturas.factura', required=True)
    line_ids   = fields.Many2many('transacciones.transaccion', string='Transacciones',
                                  domain="[('invoice_status','in',('none','partial'))]")

    def _to_cliente(self, obj):
        Cliente = self.env['clientes.cliente']
        if not obj:
            return False
        if getattr(obj, '_name', '') == 'clientes.cliente':
            return obj
        rfc = getattr(obj, 'rfc', False) or getattr(obj, 'vat', False)
        if rfc:
            cli = Cliente.search([('persona_id.rfc', '=', rfc)], limit=1)
            if cli:
                return cli
        name = getattr(obj, 'name', False)
        if name:
            return Cliente.search([('name', 'ilike', name)], limit=1)
        return False

    def action_add(self):
        self.ensure_one()
        fac = self.factura_id

        # 1) Empresa homogénea
        emps = {l.venta_id.empresa_id.id for l in self.line_ids if l.venta_id and l.venta_id.empresa_id}
        if len(emps) > 1:
            raise ValidationError(_('Todas las transacciones deben ser de la misma empresa.'))

        # 2) Cliente homogéneo
        clientes = set()
        for ln in self.line_ids:
            cli = self._to_cliente(ln.venta_id.cliente) if ln.venta_id and ln.venta_id.cliente else False
            clientes.add(cli.id if cli else None)
        if len(clientes - {None}) > 1:
            raise ValidationError(_('Todas las transacciones deben ser del mismo cliente.'))

        # 3) Crear líneas
        for ln in self.line_ids:
            if getattr(ln, 'invoice_status', '') == 'full':
                continue
            qty = (getattr(ln, 'cantidad', 0.0) or 0.0) - (getattr(ln, 'qty_invoiced', 0.0) or 0.0)
            if qty <= 0:
                continue

            cli = fac.cliente_id or (self._to_cliente(ln.venta_id.cliente) if ln.venta_id else False)
            if not fac.cliente_id and cli:
                fac.write({'cliente_id': cli.id})

            fac.line_ids.create({
                'factura_id': fac.id,
                'empresa_id': ln.venta_id.empresa_id.id if ln.venta_id and ln.venta_id.empresa_id else fac.empresa_id.id,
                'cliente_id': (fac.cliente_id or cli).id if (fac.cliente_id or cli) else False,
                'line_type': 'sale',
                'source_model': 'transacciones.transaccion',
                'source_id': ln.id,
                'sale_id': ln.venta_id.id if ln.venta_id else False,
                'transaccion_id': ln.id,
                'producto_id': ln.producto_id.id,
                'descripcion': ln.producto_id.name,
                'cantidad': qty,
                'precio': ln.precio or 0.0,
                'iva_ratio': ln.iva or 0.0,
                'ieps_ratio': ln.ieps or 0.0,
                'qty_to_invoice': qty,
            })

        return {'type': 'ir.actions.act_window_close'}