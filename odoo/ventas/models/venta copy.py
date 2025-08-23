#ventas/models/venta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date
# Modelo de ventas que gestiona información de cliente, productos, impuestos y flujo a cuentas por cobrar

class venta(models.Model):
    _name = 'ventas.ventacopy'
    _description = 'Venta de artículos'
    
    codigo = fields.Char(string="Código", required = False)
    cliente = fields.Many2one('clientes.cliente', string="Cliente", required = True)
    contrato = fields.Many2one('creditos.credito', string="Contrato", domain="['&',('cliente', '=', cliente), ('contratoactivo','=',True), ('vencimiento', '>', hoy)]" if cliente else "[('id', '=', 0)]")

    # Calcula siempre la fecha actual sin depender de otros campos
    hoy = fields.Date(compute='_compute_hoy')
    @api.depends()  # Sin dependencias, se calcula siempre
    def _compute_hoy(self):
        for record in self:
            record.hoy = date.today()
    #contrato = fields.Many2one('creditos.credito', string="Contrato")#, domain="['&',('cliente', '=', cliente), ('contratoactivo','=',True), ('vencimiento' > context_today())]" if cliente else "[('id', '=', 0)]")

    observaciones = fields.Char(string = "Observaciones", size=32)
    fecha = fields.Date(string="Fecha", default=lambda self: date.today())
    #vendedor = fields.Many2one('vendedor', string="Vendedor", required = True)
    #sucursal = fields.Many2one('sucursal', string="Sucursal", required = True)
    #empresa = fields.Many2one('empresa', string="Empresa", readonly = True)
    solicita = fields.Char(max_length=30, string="Solicita", required=True)
    importe = fields.Float(string="Importe", readonly=True)
    iva = fields.Float(string="iva", readonly=True)
    ieps = fields.Float(string="ieps", readonly=True)
    total = fields.Float(string="Total", readonly=True)
    activa = fields.Boolean(string="Activa", default = True)
    #folio = fields.Char(string="Folio", readonly=True, copy=False, default=lambda self: self.env['ir.sequence'].next_by_code('mi.modelo.folio'))

    #detalle = fields.One2many('ventas.detalleventa_ext', 'venta_id', string="Ventas")
    detalle = fields.One2many('transacciones.transaccion', 'venta_id', string="Venta")

        # Relación con Sucursal (obligatoria para prefijar el código)
    sucursal_id = fields.Many2one(
        'sucursales.sucursal', string="Sucursal",
        required=True, ondelete='restrict', index=True
    )

    # Código único de la venta (SERIE-000001)
    codigo = fields.Char(string="Código", readonly=True, copy=False, index=True)

    state = fields.Selection(
    [('draft', 'Borrador'), ('confirmed', 'Confirmada'), ('cancelled', 'Cancelada')],
    string="Estado", default='draft', required=True, index=True
    )

    is_editing = fields.Boolean(default=False, store = True)

    _sql_constraints = [
        ('venta_codigo_uniq', 'unique(codigo)', 'El código de la venta debe ser único.'),
    ]

# Limpia el contrato y filtra contratos válidos del cliente con base en vigencia y estado
    @api.onchange('cliente')
    def _onchange_cliente(self):
        self.contrato = False
        self.env.context = {}
        if self.cliente:
            # Filtramos en el servidor para que use Python y no dependa de campos no stored
            contratos_validos = self.env['creditos.credito'].search([
                ('cliente', '=', self.cliente.id),
                ('contratoactivo', '=', True),  # Aunque sea compute, aquí sí lo evalúa en Python
                ('vencimiento', '>', fields.Date.today())
            ])
            return {
                'domain': {
                    'contrato': [('id', 'in', contratos_validos.ids)]
                }
            }
        else:
            return {
                'domain': {
                    'contrato': [('id', '=', 0)]
                }
            }

# Método de pago: PPD (Crédito) o PUE (Contado)
    metododepago = fields.Selection(
        selection = [
            ("PPD", "Crédíto"),
            ("PUE", "Contado")
        ], string="Método de Pago", required=True, default="PPD", store = True
    )

# Forma de pago según catálogo SAT
    formadepago = fields.Selection(
        selection = [
            ("01", "Efectivo"),
            ("02", "Cheque Nominativo"),
            ("03", "Transferencia"),
            ("04", "Tarjeta de Crédito"),
            ("15", "Condonación"),
            ("17", "Compensación"),
            ("28", "Tarjeta de Débito"),
            ("30", "Aplicación de Anticipos"),
            ("99", "Por Definir")
        ], string="Forma de Pago", default="01"
    )

# Si es PPD, se asigna forma de pago "Por definir" (99)
    @api.onchange('metododepago')
    def _chgmpago(self):
        for record in self:
            if record.metododepago == 'PPD':
                record.formadepago = '99'
        self._apply_prices_by_method()
        self._onchange_detalles()

    """
    Qué hace: Si el método es PPD (crédito), asigna automáticamente formadepago = '99' (“Por definir”).
    Cuándo corre: Solo en UI (formulario) cuando cambias metododepago. No se ejecuta en importaciones, create RPC, tests sin UI, etc.
    Efecto: Cambia el valor en el registro en memoria del formulario; se persiste al Guardar.
    """

    def _apply_prices_by_method(self):
        """Forzar precio de líneas según PUE (contado) / PPD (crédito)."""
        for v in self:
            metodo = v.metododepago or 'PPD'
            for line in v.detalle:
                #if line.producto:
                #    line.precio = line.producto.contado if metodo == 'PUE' else line.producto.credito
                if line.producto_id:
                    line.precio = line.producto_id.contado if metodo == 'PUE' else line.producto_id.credito



# Recalcula importes, IVA, IEPS y total a partir de las líneas de detalle
    @api.onchange('detalle')
    def _onchange_detalles(self):
        self.importe = sum(line.subtotal for line in self.detalle)#importeb -> subtotal
        self.iva = sum(line.iva for line in self.detalle)
        self.ieps = sum(line.ieps for line in self.detalle)
        self.total = sum(line.importe for line in self.detalle)
    """
    Qué hace: Recalcula importe, iva, ieps, total sumando los campos calculados de cada línea (line.importeb, line.iva, line.ieps, line.importe).
    Cuándo corre: UI al agregar/editar/borrar líneas en detalle.
    Efecto: Actualiza los totales del encabezado antes de guardar.
        Nota: al ser readonly=True, los totales no se editan manualmente; este onchange les da valor.
    """

# Valida que haya al menos un producto y que cantidad y precio sean mayores a cero
    @api.constrains('detalle')
    def _check_detalle_venta(self):
        for record in self:
            if not record.detalle:
                raise ValidationError(_('No se puede guardar una venta sin al menos un producto.'))
        for linea in record.detalle:
            if linea.c_salida <= 0 or linea.precio <= 0:
                raise ValidationError(_('La Cantidad/Precio no pueden ser 0'))
            if not linea.producto_id:
                raise ValidationError(_('Debe seleccionar un producto'))
    """
    Qué hace (validación de negocio):
        Exige al menos una línea.
        Obliga cantidad > 0 y precio > 0.
        Obliga producto seleccionado.
    Cuándo corre: Al guardar (create/write) sin importar si viene de UI o de código/ORM.
    Efecto: Si falla, levanta ValidationError y no se guarda.
    """

# Envía las líneas de venta al estado de cuenta si corresponde
    def _post_to_statement_if_needed(self):
        CxC = self.env['cuentasxcobrar.cuentaxcobrar']
        for v in self:
            if v.metododepago == 'PPD' and v.contrato:
                for line in v.detalle:
                    if not CxC.search_count([('contrato_id','=',v.contrato.id), ('detalle_venta_id','=',line.id)]):
                        CxC.create_from_sale_line(v.contrato, v, line) #modelo cxcs_from_sales
                        
    """
    Qué hace: Si la venta es PPD y tiene contrato, “poste(a)” cada línea de venta al Estado de Cuenta (CxC):
        Evita duplicados buscando si ya existe una CxC con (contrato_id, detalle_venta_id).
        Si no existe, llama a CxC.create_from_sale_line(contrato, venta, line).
    Cuándo corre: Lo llamas después de crear/escribir (ver puntos 5 y 6).
    Efecto: Crea los “cargos” en CxC por cada renglón de la venta a crédito.
    """

# Sobrescribe create para enviar líneas a CxC después de crear
    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec._apply_prices_by_method()
        rec._onchange_detalles()
        # No postear CxC aquí; sólo en action_confirm
        return rec

    """
    Qué hace: Crea la venta (super), luego ejecuta _post_to_statement_if_needed().
    Cuándo corre: Siempre que haces env['ventas.venta'].create(vals).
    Efecto: Asegura que, si es PPD, la venta recién creada ya quede reflejada en CxC.
    """

# Sobrescribe write para enviar líneas a CxC después de editar
    def write(self, vals):
    # Si algún registro está confirmado, solo permitimos cambiar a 'cancelled' desde action_cancel
        if any(r.state == 'confirmed' for r in self):
            allowed_only_state_cancel = set(vals.keys()) <= {'state'} and vals.get('state') == 'cancelled'
            if not allowed_only_state_cancel:
                raise ValidationError(_("No se puede editar una venta ya confirmada. Use 'Cancelar'."))

        res = super().write(vals)

        # Si se edita en borrador (normal), mantener consistencia de precios/totales
        if 'metododepago' in vals or 'detalle' in vals:
            self._apply_prices_by_method()
            self._onchange_detalles()

        return res


    def action_cancel(self):
        """Cancela: revierte stock y borra CxC; luego marca 'cancelled'."""
        #self.write({'is_editing': False})
        for v in self:
            if v.state != 'confirmed':
                continue
            # Revertir stock de lo descontado al confirmar
            v._restore_stock_on_reopen()
            # Borrar renglones de CxC de esta venta
            v._delete_cxc_for_sale()
            # Marcar cancelada (write permitido por la regla del write)
            super(type(v), v).write({'state': 'cancelled'})
        return True

    
    def action_make_preventa(self):
        self.ensure_one()
        vals = {
            'cliente': self.cliente.id,
            'contrato': self.contrato.id if self.contrato else False,
            'fecha': fields.Date.today(),
            'sucursal_id': self.sucursal_id.id,
            'metododepago': self.metododepago,
            'formadepago': self.formadepago,
            'solicita': self.solicita,
            'observaciones': self.observaciones,
        }
        prev = self.env['ventas.preventa'].create(vals)
        Det = self.env['ventas.detalleventa_ext']
        for line in self.detalle:
            Det.create({
                'venta_id': prev.id,   # reusa el many2one; en preventa funciona por herencia de campos
                'producto': line.producto_id.id,
                'cantidad': line.c_salida,
                'precio': line.precio,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Preventa'),
            'res_model': 'ventas.preventa',
            'res_id': prev.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _check_stock_before_confirm(self):
        """Verifica stock por sucursal/producto. Error si no alcanza."""
        Stock = self.env['stock.sucursal.producto']
        for v in self:
            if not v.sucursal_id:
                raise ValidationError(_("Debe seleccionar la sucursal."))
            prod_ids = v.detalle.mapped('producto').ids
            stocks = Stock.search([
                ('sucursal_id', '=', v.sucursal_id.id),
                ('producto_id', 'in', prod_ids),
            ])
            stock_map = {(s.producto_id.id): s for s in stocks}
            for line in v.detalle:
                sline = stock_map.get(line.producto_id.id)
                qty_avail = sline.c_salida if sline else 0.0
                if line.c_salida > qty_avail:
                    raise ValidationError(_(
                        "Stock insuficiente en %s para %s: requerido %.2f, disponible %.2f"
                    ) % (v.sucursal_id.display_name, line.producto_id.display_name, line.c_salida, qty_avail))



    def _deduct_stock_on_confirm(self):
        """Descuenta stock por sucursal/producto (evita negativos)."""
        Stock = self.env['stock.sucursal.producto']
        for v in self:
            prod_ids = v.detalle.mapped('producto').ids
            stocks = Stock.search([
                ('sucursal_id', '=', v.sucursal_id.id),
                ('producto_id', 'in', prod_ids),
            ])
            stock_map = {(s.producto_id.id): s for s in stocks}
            for line in v.detalle:
                sline = stock_map.get(line.producto_id.id)
                if not sline:
                    sline = Stock.create({
                        "sucursal_id": v.sucursal_id.id,
                        "producto_id": line.producto_id.id,
                        "cantidad": 0.0,
                    })
                    stock_map[line.producto.id] = sline
                if sline.cantidad < line.cantidad:
                    raise ValidationError(_(
                        "Stock insuficiente al confirmar: %s (solicitado %.2f, disponible %.2f)"
                    ) % (line.producto.display_name, line.c_salida, sline.cantidad))
                sline.cantidad = sline.cantidad - line.c_salida

    def _restore_stock_on_reopen(self):
        """Devuelve al stock lo descontado en la confirmación (usa líneas actuales)."""
        Stock = self.env['stock.sucursal.producto']
        for v in self:
            if v.state != 'confirmed':
                continue
            prod_ids = v.detalle.mapped('producto').ids
            stocks = Stock.search([
                ('sucursal_id', '=', v.sucursal_id.id),
                ('producto_id', 'in', prod_ids),
            ])
            stock_map = {(s.producto_id.id): s for s in stocks}
            for line in v.detalle:
                sline = stock_map.get(line.producto_id.id)
                if not sline:
                    sline = Stock.create({
                        "sucursal_id": v.sucursal_id.id,
                        "producto_id": line.producto_id.id,
                        "cantidad": 0.0,
                    })
                    stock_map[line.producto_id.id] = sline
                sline.cantidad = sline.cantidad + line.c_salida


    def action_confirm(self):
        """Confirma: genera codigo si falta, verifica stock, descuenta y postea CxC (si PPD)."""
        for v in self:
            if v.state == 'confirmed':
                continue

            # 1) Generar codigo si no existe (SERIE-000001)
            if not v.codigo:
                serie = (v.sucursal_id.serie or 'XX') if v.sucursal_id else 'XX'
                seq = self.env['ir.sequence'].next_by_code('seq_venta_code') or '/'
                num = (seq.split('/')[-1]).zfill(6)
                v.write({'codigo': f"{serie}-{num}"})  # write para persistir

            # 2) Stock
            v._check_stock_before_confirm()
            v._deduct_stock_on_confirm()

            # 3) Totales finales
            v._apply_prices_by_method()
            v._onchange_detalles()

            # 4) CxC (solo al confirmar)
            v._post_to_statement_if_needed()

            # 5) Estado
            v.state = 'confirmed'
        return True




    """
    Qué hace: Escribe cambios (super) y luego ejecuta _post_to_statement_if_needed().
    Cuándo corre: En cualquier edición de la venta (cambio de método, contrato, líneas, etc.).
    Efecto importante: Si agregas nuevas líneas o cambias de PUE→PPD con contrato, poste(a) lo que falte.
        Evita duplicar gracias al search_count con (contrato_id, detalle_venta_id).
    """

    def _delete_cxc_for_sale(self):
        """Elimina renglones CxC originados por esta venta (si existen)."""
        CxC = self.env['cuentasxcobrar.cuentaxcobrar']
        for v in self:
            to_del = CxC.search([('venta_id', '=', v.id)])
            # Si quieres proteger cuando hay abonos, valida aquí antes de borrar.
            to_del.unlink()