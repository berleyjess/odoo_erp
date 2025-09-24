# wizards/add_from_sales.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class WizAddSales(models.TransientModel):
    _name = 'facturas.wiz.add.sales'
    _description = 'Agregar ventas completas'

    factura_id = fields.Many2one('facturas.factura', required=True)
    venta_ids  = fields.Many2many('ventas.venta', string='Ventas',
                                  domain="[('invoice_status2','in',('none','partial'))]")

    # --- Helper: normaliza a clientes.cliente ---
    def _to_cliente(self, obj):
        """Devuelve un recordset de clientes.cliente o False a partir de:
           - clientes.cliente (lo mismo)
           - res.partner (usa vat como RFC)
           - objectos con campo rfc / name
        """
        if not obj:
            return False
        Cliente = self.env['clientes.cliente']
        # ya es cliente
        if getattr(obj, '_name', '') == 'clientes.cliente':
            return obj
        # tiene RFC directo
        rfc = getattr(obj, 'rfc', False) or getattr(obj, 'vat', False)
        if rfc:
            cli = Cliente.search([('persona_id.rfc', '=', rfc)], limit=1)
            if cli:
                return cli
        # fallback por nombre
        name = getattr(obj, 'name', False)
        if name:
            return Cliente.search([('name', 'ilike', name)], limit=1)
        return False

    def action_add(self):
        self.ensure_one()
        fac = self.factura_id

        # 1) Validar empresas homogéneas
        empresas = {v.empresa_id.id for v in self.venta_ids if v.empresa_id}
        if len(empresas) > 1:
            raise ValidationError(_('Selecciona ventas de la misma empresa.'))

        # 2) Determinar/validar cliente
        encabezado_cli = fac.cliente_id
        for v in self.venta_ids:
            venta_cli = self._to_cliente(getattr(v, 'cliente', False))
            if encabezado_cli and venta_cli and venta_cli.id != encabezado_cli.id:
                raise ValidationError(_('Todas las ventas deben ser del mismo cliente que el encabezado.'))

        # Si el encabezado no tiene cliente, toma el de la primera venta válida
        if not fac.cliente_id:
            first_cli = False
            for v in self.venta_ids:
                first_cli = self._to_cliente(getattr(v, 'cliente', False))
                if first_cli:
                    break
            if not first_cli:
                raise UserError(_('No se pudo determinar el cliente.'))
            fac.write({'cliente_id': first_cli.id})

        # 3) Crear líneas a partir de cada detalle de venta
        for v in self.venta_ids:
            venta_cli = self._to_cliente(getattr(v, 'cliente', False)) or fac.cliente_id
            for ln in getattr(v, 'detalle', []):
                if getattr(ln, 'invoice_status', '') == 'full':
                    continue
                qty = (getattr(ln, 'cantidad', 0.0) or 0.0) - (getattr(ln, 'qty_invoiced', 0.0) or 0.0)
                if qty <= 0:
                    continue

                fac.line_ids.create({
                    'factura_id': fac.id,
                    'empresa_id': v.empresa_id.id,
                    'cliente_id': venta_cli.id if venta_cli else False,
                    'line_type': 'sale',
                    'source_model': 'transacciones.transaccion',  # deja como lo usabas
                    'source_id': ln.id,
                    'sale_id': v.id,
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