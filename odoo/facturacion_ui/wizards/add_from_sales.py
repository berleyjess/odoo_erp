# wizards/add_from_sales.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class WizAddSales(models.TransientModel):
    _name = 'facturas.wiz.add.sales'
    _description = 'Agregar ventas completas'

    factura_id = fields.Many2one('facturas.factura', required=True)
    venta_ids = fields.Many2many(
        'ventas.venta', 
        string='Ventas',
        domain="[('invoice_status2','in',('none','partial'))]"
    )

    @api.onchange('factura_id')
    def _onchange_factura_id(self):
        """Filtra ventas disponibles"""
        if not self.factura_id:
            return
        
        domain = [
            ('invoice_status2', 'in', ('none', 'partial')),
            ('state', '=', 'confirmed')  # Solo ventas confirmadas
        ]
        
        if self.factura_id.empresa_id:
            domain.append(('empresa_id', '=', self.factura_id.empresa_id.id))
        
        if self.factura_id.sucursal_id:
            domain.append(('sucursal_id', '=', self.factura_id.sucursal_id.id))
        
        return {'domain': {'venta_ids': domain}}

    def _to_cliente(self, obj):
        """Devuelve un recordset de clientes.cliente o False"""
        if not obj:
            return False
        Cliente = self.env['clientes.cliente']
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

        # Validar que las ventas no estén completamente facturadas
        full_invoiced = self.venta_ids.filtered(lambda x: x.invoice_status2 == 'full')
        if full_invoiced:
            nombres = [ (v.display_name or _("Venta #%s") % v.id) for v in full_invoiced ]
            detalle = "\n- " + "\n- ".join(map(str, nombres))
            raise UserError(_("No puedes agregar ventas ya facturadas.\nEstas ya están totalmente facturadas:%s") % detalle)

        # Validar empresas homogéneas
        empresas = {v.empresa_id.id for v in self.venta_ids if v.empresa_id}
        if len(empresas) > 1:
            raise ValidationError(_('Selecciona ventas de la misma empresa.'))

        # Determinar/validar cliente
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
                raise ValidationError(_('No se pudo determinar el cliente.'))
            fac.write({'cliente_id': first_cli.id})

        # Crear líneas a partir de cada detalle de venta
        created_lines = []
        for v in self.venta_ids:
            venta_cli = self._to_cliente(getattr(v, 'cliente', False)) or fac.cliente_id
            
            for ln in getattr(v, 'detalle', []):
                # Verificar estado de facturación de la transacción
                if getattr(ln, 'invoice_status', '') == 'full':
                    continue
                    
                # Calcular cantidad disponible
                qty_available = getattr(ln, 'qty_available', 0.0)
                if not qty_available:
                    qty_available = (getattr(ln, 'cantidad', 0.0) or 0.0) - (getattr(ln, 'qty_invoiced', 0.0) or 0.0)
                
                if qty_available <= 0:
                    continue

                new_line = fac.line_ids.create({
                    'factura_id': fac.id,
                    'empresa_id': v.empresa_id.id,
                    'cliente_id': venta_cli.id if venta_cli else False,
                    'line_type': 'sale',
                    'source_model': 'transacciones.transaccion',
                    'source_id': ln.id,
                    'sale_id': v.id,
                    'transaccion_id': ln.id,
                    'producto_id': ln.producto_id.id,
                    'descripcion': ln.producto_id.name,
                    'cantidad': qty_available,  # Solo cantidad disponible
                    'precio': ln.precio or 0.0,
                    'iva_ratio': ln.iva or 0.0,
                    'ieps_ratio': ln.ieps or 0.0,
                    'qty_to_invoice': qty_available,
                })
                created_lines.append(new_line)

        if not created_lines:
            raise ValidationError(_('No se agregó ninguna línea. Verifica que haya cantidades disponibles para facturar.'))

        return {'type': 'ir.actions.act_window_close'}