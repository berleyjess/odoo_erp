# wizards/add_from_lines.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError

class WizAddLines(models.TransientModel):
    _name = 'facturas.wiz.add.lines'
    _description = 'Agregar transacciones sueltas'

    factura_id = fields.Many2one('facturas.factura', required=True)
    line_ids = fields.Many2many(
        'transacciones.transaccion', 
        string='Transacciones',
        domain="[('invoice_status','in',('none','partial'))]"
    )

    @api.onchange('factura_id')
    def _onchange_factura_id(self):
        if not self.factura_id:
            return
        # transacciones ya agregadas a esta factura
        used_tx = self.env['facturas.factura.line'].sudo().search([
            ('factura_id', '=', self.factura_id.id),
            ('source_model', '=', 'transacciones.transaccion'),
        ]).mapped('source_id')
    
        domain = [
            ('invoice_status', 'in', ('none', 'partial')),   # ⬅️ no “full”
            ('id', 'not in', used_tx),                      # ⬅️ no mostrar ya agregadas
        ]
        if self.factura_id.empresa_id:
            domain.append(('venta_id.empresa_id', '=', self.factura_id.empresa_id.id))
        if self.factura_id.sucursal_id:
            domain.append(('venta_id.sucursal_id', '=', self.factura_id.sucursal_id.id))
        return {'domain': {'line_ids': domain}}


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

        # Validar que las transacciones no estén completamente facturadas
        full_invoiced = self.line_ids.filtered(lambda x: x.invoice_status == 'full')
        if full_invoiced:
            nombres = [ (r.display_name or _("Transacción #%s") % r.id) for r in full_invoiced ]
            detalle = "\n- " + "\n- ".join(map(str, nombres))
            raise UserError(_("No puedes agregar transacciones ya facturadas.\nEstas ya están totalmente facturadas:%s") % detalle)

        # Validar empresa homogénea
        emps = {l.venta_id.empresa_id.id for l in self.line_ids if l.venta_id and l.venta_id.empresa_id}
        if len(emps) > 1:
            raise ValidationError(_('Todas las transacciones deben ser de la misma empresa.'))

        # Validar cliente homogéneo
        clientes = set()
        for ln in self.line_ids:
            cli = self._to_cliente(ln.venta_id.cliente) if ln.venta_id and ln.venta_id.cliente else False
            clientes.add(cli.id if cli else None)
        if len(clientes - {None}) > 1:
            raise ValidationError(_('Todas las transacciones deben ser del mismo cliente.'))

        # Crear líneas con validación de disponibilidad
        created_lines = []
        for ln in self.line_ids:
            # Calcula cantidad disponible
            qty_available = ln.qty_available or ((ln.cantidad or 0.0) - (ln.qty_invoiced or 0.0))
            
            if qty_available <= 0:
                continue

            cli = fac.cliente_id or (self._to_cliente(ln.venta_id.cliente) if ln.venta_id else False)
            if not fac.cliente_id and cli:
                fac.write({'cliente_id': cli.id})

            new_line = fac.line_ids.create({
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
                'cantidad': qty_available,  # Solo la cantidad disponible
                'precio': ln.precio or 0.0,
                'iva_ratio': ln.iva or 0.0,
                'ieps_ratio': ln.ieps or 0.0,
                'qty_to_invoice': qty_available,
            })
            created_lines.append(new_line)

        if not created_lines:
            raise ValidationError(_('No se agregó ninguna línea. Verifica que haya cantidades disponibles para facturar.'))

        return {'type': 'ir.actions.act_window_close'}