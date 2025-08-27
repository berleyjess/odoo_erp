#ventas/models/venta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date

class venta(models.Model):
    _name = 'ventas.venta'
    _description = 'Venta de artículos'
    
    cliente = fields.Many2one('clientes.cliente', string="Cliente", required=True)
    contrato = fields.Many2one('creditos.credito', string="Contrato",
                               domain="[('cliente', '=', cliente), ('contratoactivo','=',True), ('vencimiento', '>', context_today())]" if cliente else "[('id', '=', 0)]")

    # Calcula siempre la fecha actual sin depender de otros campos
    hoy = fields.Date(compute='_compute_hoy')
    @api.depends()
    def _compute_hoy(self):
        for record in self:
            record.hoy = date.today()

    observaciones = fields.Char(string="Observaciones", size=48)
    fecha = fields.Date(string="Fecha", default=lambda self: date.today())
    importe = fields.Float(string="Importe", readonly=True, store=True, compute='_add_detalles')
    iva = fields.Float(string="iva", readonly=True, store=True, compute='_add_detalles')
    ieps = fields.Float(string="ieps", readonly=True, store=True, compute='_add_detalles')
    total = fields.Float(string="Total", readonly=True, store=True, compute='_add_detalles')
    activa = fields.Boolean(string="Activa", default=True)

    detalle = fields.One2many('transacciones.transaccion', 'venta_id', string="Venta")

    # Sucursal de la venta
    sucursal_id = fields.Many2one('sucursales.sucursal', string="Sucursal",
                                  required=True, ondelete='restrict', index=True)

    # Folio
    codigo = fields.Char(string="Folio", readonly=True, copy=False, index=True)

    state = fields.Selection(
        [('draft', 'Borrador'), ('confirmed', 'Confirmada'), ('cancelled', 'Cancelada'), ('invoiced', 'Facturada')],
        string="Estado", default='draft', required=True, index=True
    )

    is_editing = fields.Boolean(default=False, store=True)

    # NEW: para no aplicar/revertir stock dos veces
    stock_aplicado = fields.Boolean(default=False, copy=False)

    _sql_constraints = [
        ('venta_codigo_uniq', 'unique(codigo)', 'El código de la venta debe ser único.'),
    ]

    @api.onchange('cliente')
    def _onchange_cliente(self):
        self.contrato = False
        # (dejas tu filtrado por dominio server-side si luego lo reactivas)

    # Método de pago
    metododepago = fields.Selection(
        selection=[("PPD", "Crédíto"), ("PUE", "Contado")],
        string="Método de Pago", required=True, default="PPD", store=True
    )

    # Forma de pago SAT
    formadepago = fields.Selection(
        selection=[
            ("01", "Efectivo"), ("02", "Cheque Nominativo"), ("03", "Transferencia"),
            ("04", "Tarjeta de Crédito"), ("15", "Condonación"), ("17", "Compensación"),
            ("28", "Tarjeta de Débito"), ("30", "Aplicación de Anticipos"), ("99", "Por Definir")
        ],
        string="Forma de Pago", default="01"
    )

    @api.onchange('metododepago')
    def _chgmpago(self):
        for record in self:
            if record.metododepago == 'PPD':
                record.formadepago = '99'
        self._apply_prices_by_method()

    def _apply_prices_by_method(self):
        """Forzar precio de líneas según PUE/PPD (mantengo tu lógica)."""
        for v in self:
            metodo = v.metododepago or 'PPD'
            for line in v.detalle:
                if line.producto_id:
                    line.precio = line.producto_id.contado if metodo == 'PUE' else line.producto_id.credito

    @api.depends('detalle.subtotal', 'detalle.iva_amount', 'detalle.ieps_amount', 'detalle.importe')
    def _add_detalles(self):
        for rec in self:
            rec.importe = sum(l.subtotal for l in rec.detalle)
            rec.iva     = sum(l.iva_amount for l in rec.detalle)
            rec.ieps    = sum(l.ieps_amount for l in rec.detalle)
            rec.total   = sum(l.importe for l in rec.detalle)

    @api.constrains('detalle')
    def _check_detalle_venta(self):
        for record in self:
            if not record.detalle:
                raise ValidationError(_('No se puede guardar una venta sin al menos un producto.'))
            for linea in record.detalle:
                if linea.cantidad <= 0 or linea.precio <= 0:
                    raise ValidationError(_('La Cantidad/Precio no pueden ser 0'))
                if not linea.producto_id:
                    raise ValidationError(_('Debe seleccionar un producto'))

    def action_open_edit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Editar Venta',
            'res_model': 'ventas.venta',
            'view_mode': 'form',
            'view_id': self.env.ref('ventas.view_venta_form').id,
            'res_id': self.id,
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    # =========================
    # Lógica de inventario
    # =========================

    def _get_stock_moves(self):
        """
        Agrupa las SALIDAS por producto para esta venta.
        Considera solo líneas con cantidad > 0 y tipo 'Salida'.
        Usamos preferentemente line.stock == '2' (si tu compute existe);
        si no existe, caemos a tipo == '1' (Venta).
        """
        self.ensure_one()
        moves = {}
        for line in self.detalle:
            es_salida = False
            # preferente: campo 'stock' (2 = Salida)
            if hasattr(line, 'stock') and line.stock == '2':
                es_salida = True
            # fallback: campo 'tipo' (1 = Venta)
            elif hasattr(line, 'tipo') and line.tipo == '1':
                es_salida = True

            if es_salida and line.cantidad > 0 and line.producto_id:
                pid = line.producto_id.id
                moves[pid] = moves.get(pid, 0.0) + line.cantidad
        return moves

    def _check_stock_before_confirm(self):
        Stock = self.env['stock.sucursal.producto']
        for sale in self:
            if not sale.sucursal_id:
                raise ValidationError(_("Debe seleccionar la sucursal de la venta."))
            moves = sale._get_stock_moves()
            for pid, qty in moves.items():
                prod = self.env['productos.producto'].browse(pid)
                disponible = Stock.get_available(sale.sucursal_id, prod)
                if disponible < qty:
                    raise ValidationError(_(
                        "Stock insuficiente para confirmar.\nProducto: %(prod)s\nSucursal: %(suc)s\nDisponible: %(disp).4f\nRequerido: %(req).4f"
                    ) % {
                        "prod": prod.display_name,
                        "suc": sale.sucursal_id.display_name,
                        "disp": disponible,
                        "req": qty,
                    })
            # Validación suave: las líneas deben coincidir en sucursal (si traen ese campo)
            for line in sale.detalle:
                if hasattr(line, 'sucursal_id') and line.sucursal_id and line.sucursal_id != sale.sucursal_id:
                    raise ValidationError(_("La sucursal de cada línea debe coincidir con la sucursal de la venta."))

    def _apply_stock_on_confirm(self):
        Stock = self.env['stock.sucursal.producto']
        for sale in self:
            moves = sale._get_stock_moves()
            for pid, qty in moves.items():
                prod = self.env['productos.producto'].browse(pid)
                Stock.remove_stock(sale.sucursal_id, prod, qty)
            sale.stock_aplicado = True

    def _revert_stock_on_cancel(self):
        Stock = self.env['stock.sucursal.producto']
        for sale in self:
            if not sale.stock_aplicado:
                continue
            moves = sale._get_stock_moves()
            for pid, qty in moves.items():
                prod = self.env['productos.producto'].browse(pid)
                Stock.add_stock(sale.sucursal_id, prod, qty)
            sale.stock_aplicado = False

    # Acciones de workflow
    def action_confirm(self):
        for sale in self:
            if sale.state != 'draft':
                raise ValidationError(_("Solo se puede confirmar desde Borrador."))
        self._check_stock_before_confirm()
        self._apply_stock_on_confirm()
        self.write({'state': 'confirmed'})
        return True

    def action_cancel(self):
        for sale in self:
            if sale.state not in ('confirmed', 'invoiced'):
                raise ValidationError(_("Solo se puede cancelar una venta Confirmada o Facturada."))
        self._revert_stock_on_cancel()
        self.write({'state': 'cancelled'})
        return True

    def write(self, vals):
        if any(r.state == 'cancelled' for r in self):
            raise ValidationError(_("Venta cancelada: no se permite editar."))
        return super().write(vals)
