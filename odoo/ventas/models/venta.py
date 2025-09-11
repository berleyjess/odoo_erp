#ventas/models/venta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date
from odoo import SUPERUSER_ID
from ..services.invoicing_bridge import create_invoice_from_sale

class venta(models.Model):
    _name = 'ventas.venta'
    _description = 'Venta de artículos'
    _check_company_auto = True  # buenas prácticas multiempresa
    
    cliente = fields.Many2one('clientes.cliente', string="Cliente", required=True)
    contrato = fields.Many2one('creditos.credito', string="Contrato",
                               domain="[('cliente', '=', cliente), ('status','=','active'), ('vencimiento', '>', context_today())]" if cliente else "[('id', '=', 0)]")

    # Calcula siempre la fecha actual sin depender de otros campos
    hoy = fields.Date(compute='_compute_hoy')
    @api.depends()
    def _compute_hoy(self):
        for record in self:
            record.hoy = date.today()

    def action_noop(self):
        """Usado por los tiles de cabecera: no hace nada."""
        return False


    observaciones = fields.Char(string="Observaciones", size=48)
    fecha = fields.Date(string="Fecha", readonly=True, copy=False, index=True)
    importe = fields.Float(string="Importe", readonly=True, store=True, compute='_add_detalles')
    iva = fields.Float(string="iva", readonly=True, store=True, compute='_add_detalles')
    ieps = fields.Float(string="ieps", readonly=True, store=True, compute='_add_detalles')
    total = fields.Float(string="Total", readonly=True, store=True, compute='_add_detalles')
    activa = fields.Boolean(string="Activa", default=True)

    detalle = fields.One2many('transacciones.transaccion', 'venta_id', string="Venta")

    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company, index=True)

    

    # Empresa con default por ID
    empresa_id = fields.Many2one(
        'empresas.empresa', string='Empresa', required=True,
        default=lambda self: self.env.user.empresa_actual_id.id,
        check_company=True, # ⬅️ Entra aquí y valida contra empresas.empresa.company_id
    )

    # Sucursal con default por ID
    sucursal_id = fields.Many2one(
        'sucursales.sucursal', string='Sucursal', required=True,
        default=lambda self: self.env.user.sucursal_actual_id.id,
    )

    @api.onchange('empresa_id')
    def _onchange_empresa_id(self):
        if self.empresa_id:
            # si quieres que la venta “pertenezca” a la misma compañía operativa que la empresa
            self.company_id = self.empresa_id.company_id
        # coherencia sucursal-empresa
        if self.sucursal_id and self.sucursal_id.empresa != self.empresa_id:
            self.sucursal_id = False


    @api.onchange('sucursal_id')
    def _onchange_sucursal(self):
        if self.sucursal_id:
            self.empresa_id = self.sucursal_id.empresa

    @api.constrains('sucursal_id', 'empresa_id')
    def _check_sucursal_empresa(self):
        for r in self:
            if r.sucursal_id and r.sucursal_id.empresa != r.empresa_id:
                raise ValidationError(_("La sucursal no pertenece a la empresa seleccionada."))

    # Folio
    codigo = fields.Char(string="Folio", readonly=True, copy=False, index=True)

    state = fields.Selection(
        [('draft', 'Borrador'), ('confirmed', 'Confirmada'), ('cancelled', 'Cancelada'), ('invoiced', 'Facturada')],
        string="Estado", default='draft', required=True, index=True
    )

    # Enlace con la factura generada (OCA/Enterprise)
    move_id = fields.Many2one('account.move', string='Factura', copy=False, readonly=True, check_company=True, # ⬅️ Garantiza que la factura sea de la misma compañía que la venta
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

    def write(self, vals):
        res = super().write(vals)
        if self.contrato:
            self.contrato._calc_saldoporventas()
        return res
    
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

    def action_open_payments(self):
        """Smart button: abre pagos ligados a la factura."""
        self.ensure_one()
        if not self.move_id:
            raise ValidationError(_('No hay factura vinculada para ver pagos.'))
        payments = self.env['account.payment'].search([('reconciled_invoice_ids', 'in', self.move_id.id)])
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Pagos'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', payments.ids)],
            'target': 'current',
        }
        return action

    def action_open_contrato(self):
        """Smart button: abre el contrato (crédito) relacionado."""
        self.ensure_one()
        if not self.contrato:
            raise ValidationError(_('No hay contrato relacionado.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contrato'),
            'res_model': self.contrato._name,
            'view_mode': 'form',
            'res_id': self.contrato.id,
            'target': 'current',
        }

    # Acciones de workflow
    def action_confirm(self):
        for sale in self:
            if sale.state != 'draft':
                raise ValidationError(_("Solo se puede confirmar desde Borrador."))
        self._check_stock_before_confirm()
        self._apply_stock_on_confirm()

        today = fields.Date.context_today(self)
        for sale in self:
            vals = {'state': 'confirmed'}
            if not sale.fecha:
                vals['fecha'] = today
            if not sale.codigo:
                vals['codigo'] = sale._next_folio()
            sale.sudo().write(vals)
            #sale.write(vals)  # escribe con el usuario real

        return True

    def action_cancel(self):
        for sale in self:
            if sale.state not in ('confirmed', 'invoiced'):
                raise ValidationError(_("Solo se puede cancelar una venta Confirmada o Facturada."))
        self._revert_stock_on_cancel()
        self.write({'state': 'cancelled'})
        return True

    def write(self, vals):
        for rec in self:
            if rec.state == 'cancelled':
                raise ValidationError(_("Venta cancelada: no se permite editar."))

            # ✅ Solo valida permisos si se intenta cambiar empresa/sucursal
            if 'empresa_id' in vals or 'sucursal_id' in vals:
                rec._check_user_company_branch(vals=vals)

        return super().write(vals)

    
    def _check_user_company_branch(self, vals=None):
        user = self.env.user
        for rec in (self if self else self.browse()):
            empresa_id = (vals or {}).get('empresa_id', rec.empresa_id.id)
            sucursal_id = (vals or {}).get('sucursal_id', rec.sucursal_id.id)

            if empresa_id and empresa_id not in user.empresas_ids.ids:
                raise ValidationError(_("No tienes permiso para usar la empresa seleccionada."))

            if sucursal_id and sucursal_id not in user.sucursales_ids.ids:
                raise ValidationError(_("No tienes permiso para usar la sucursal seleccionada."))

            if empresa_id and sucursal_id:
                suc = self.env['sucursales.sucursal'].browse(sucursal_id)
                if suc.empresa.id != empresa_id:
                    raise ValidationError(_("La sucursal '%s' no pertenece a la empresa seleccionada.") % (suc.display_name,))

    @api.model
    def create(self, vals):
        vals.setdefault('empresa_id', self.env.user.empresa_actual_id.id)
        vals.setdefault('sucursal_id', self.env.user.sucursal_actual_id.id)

        if vals.get('empresa_id'):
            emp = self.env['empresas.empresa'].browse(vals['empresa_id'])
            if emp and emp.company_id:
                vals['company_id'] = emp.company_id.id  # venta y empresa operativa alineadas

        self._check_user_company_branch(vals=vals)
        return super().create(vals)




    def _next_folio(self):
        """Intenta usar una secuencia; ajusta el código si la tuya se llama distinto."""
        # Cambia 'ventas.venta.folio' por el código real de tu secuencia si ya existe
        seq_code_candidates = ['ventas.venta.folio', 'ventas.venta', 'seq.ventas.venta']
        IrSeq = self.env['ir.sequence']
        for code in seq_code_candidates:
            nxt = IrSeq.next_by_code(code)
            if nxt:
                return nxt
        # Si no hay secuencia configurada, arma un folio simple y único como fallback
        return self.env['ir.sequence'].next_by_code('base.sequence_mixin') or self._generate_default_folio()

    def _generate_default_folio(self):
        # Fallback ultra simple (no depende de data extra)
        return f"V-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _check_user_company_branch(self, vals=None):
        # No validar para superusuario
        if self.env.uid == SUPERUSER_ID:
            return

        user = self.env.user
        for r in (self if self else self.browse()):
            empresa_id  = (vals or {}).get('empresa_id',  r.empresa_id.id)
            sucursal_id = (vals or {}).get('sucursal_id', r.sucursal_id.id)

            if empresa_id and empresa_id not in user.empresas_ids.ids:
                raise ValidationError(_("No tienes permiso para usar la empresa seleccionada."))
            if sucursal_id and sucursal_id not in user.sucursales_ids.ids:
                raise ValidationError(_("No tienes permiso para usar la sucursal seleccionada."))

            # Consistencia empresa–sucursal
            if empresa_id and sucursal_id:
                suc = self.env['sucursales.sucursal'].browse(sucursal_id)
                if suc.empresa.id != empresa_id:
                    raise ValidationError(_("La sucursal '%s' no pertenece a la empresa seleccionada.") % (suc.display_name,))

    # Estado/folio CFDI
    cfdi_state = fields.Selection([
        ('none', 'Sin CFDI'),
        ('to_stamp', 'Por timbrar'),
        ('stamped', 'Timbrado'),
        ('to_cancel', 'Por cancelar'),
        ('canceled', 'Cancelado'),
    ], default='none', string="Estado CFDI", copy=False)

    cfdi_uuid = fields.Char(string="UUID", copy=False, readonly=True)
    cfdi_tipo = fields.Selection([('I','Ingreso'),('E','Egreso'),('P','Pago')], string="Tipo CFDI", copy=False)
    cfdi_relacion_tipo = fields.Selection([
        ('01','Nota de crédito de los documentos relacionados'),
        ('02','Nota de débito de los documentos relacionados'),
        ('03','Devolución de mercancía sobre facturas o traslados previos'),
        ('04','Sustitución de los CFDI previos'),
        ('05','Traslados de mercancias facturados previamente'),
        ('06','Factura generada por los traslados previos'),
        ('07','CFDI por aplicación de anticipo'),
    ], string="Tipo de relación", copy=False)
    cfdi_relacion_ventas_ids = fields.Many2many('ventas.venta', 'venta_cfdi_rel_m2m', 'venta_id', 'rel_id',
                                                string="CFDIs relacionados", copy=False)

    def action_open_cfdi_wizard(self):
        """Abre el wizard para capturar Uso CFDI / Método / Relación, etc."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generar CFDI'),
            'res_model': 'ventas.cfdi.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_id': self.id,
                'default_metodo_pago': self.metododepago or 'PPD',
                'default_forma_pago': self.formadepago or False,
            },
        }
    
    def _to_cfdi_conceptos(self):
     """Convierte líneas de venta a conceptos CFDI (placeholder simple)."""
     conceptos = []
     for l in self.detalle:
        if not l.producto_id:
            continue
        clave_prod_serv = getattr(l.producto_id, 'sat_clave_prod_serv', None) or '01010101'
        clave_unidad = getattr(l.producto_id, 'sat_clave_unidad', None) or 'H87'
        no_ident = getattr(l.producto_id, 'default_code', None) or str(l.producto_id.id)
        descripcion = getattr(l.producto_id, 'name', 'Producto')
        cantidad = l.cantidad or 1.0
        precio = l.precio or 0.0
        subtotal = getattr(l, 'subtotal', cantidad * precio)
        iva_amt = getattr(l, 'iva_amount', 0.0)
        ieps_amt = getattr(l, 'ieps_amount', 0.0)
        impuestos = {'traslados': []}
        if iva_amt:
            impuestos['traslados'].append({
                'impuesto': '002',      # IVA
                'tipo_factor': 'Tasa',
                'tasa_cuota': 0.16,     # ajusta según tu línea
                'base': subtotal,
                'importe': iva_amt,
            })
        if ieps_amt:
            impuestos['traslados'].append({
                'impuesto': '003',      # IEPS
                'tipo_factor': 'Tasa',
                'tasa_cuota': 0.08,     # ejemplo
                'base': subtotal,
                'importe': ieps_amt,
            })

        conceptos.append({
            'clave_sat': clave_prod_serv,
            'clave_unidad': clave_unidad,
            'no_identificacion': no_ident,
            'descripcion': descripcion,
            'cantidad': cantidad,
            'valor_unitario': precio,
            'importe': subtotal + iva_amt + ieps_amt,
            'objeto_imp': '02',  # gravado
            'impuestos': impuestos,
        })
     return conceptos

     # Contador de adjuntos (smart button)
    attachment_count = fields.Integer(compute='_compute_attachment_count')

    def _compute_attachment_count(self):
        Att = self.env['ir.attachment']
        for r in self:
            r.attachment_count = Att.search_count([('res_model', '=', r._name), ('res_id', '=', r.id)])

    def action_open_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Adjuntos'),
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',  # <- IMPORTANTE
            'domain': [('res_model', '=', self._name), ('res_id', 'in', self.ids)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
            'target': 'current',
        }

    def action_download_cfdi(self):
        self.ensure_one()
        Att = self.env['ir.attachment']
        att = False
        # 1) Preferir adjuntos del account.move
        if self.move_id:
            att = Att.search([
                ('res_model', '=', 'account.move'),
                ('res_id', '=', self.move_id.id),
                ('mimetype', '=', 'application/xml'),
            ], limit=1, order='id desc')
        # 2) Complemento de pagos: buscar XML en movimientos de pago ligados a la factura
        if not att and self.move_id:
            Pay = self.env['account.payment']
            payments = Pay.search([('reconciled_invoice_ids', 'in', self.move_id.id), ('state', '=', 'posted')], limit=5)
            if payments:
                att = Att.search([
                    ('res_model', '=', 'account.move'),
                    ('res_id', 'in', payments.mapped('move_id').ids),
                    ('mimetype', '=', 'application/xml'),
                ], limit=1, order='id desc')
        # 3) Fallback a adjuntos en la propia venta (legacy dummy)
        if not att:
            att = Att.search([
                ('res_model', '=', 'ventas.venta'),
                ('res_id', '=', self.id),
                ('mimetype', '=', 'application/xml'),
            ], limit=1, order='id desc')
        if not att:
            # Busca por doc de tu engine como fallback
            att = Att.search([
                ('res_model', '=', 'mx.cfdi.document'),
                ('res_id', 'in', self.env['mx.cfdi.document'].search([
                    ('origin_model', '=', 'ventas.venta'),
                    ('origin_id', '=', self.id),
                    ('uuid', '=', self.cfdi_uuid),
                ]).ids),
                ('mimetype', '=', 'application/xml'),
            ], limit=1, order='id desc')
        if not att:
            raise ValidationError(_("No hay XML adjunto para esta venta."))

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{att.id}?download=true',
            'target': 'self',
        }

    def action_cancel_cfdi(self):
        self.ensure_one()
        if not self.cfdi_uuid:
            raise ValidationError(_('No hay UUID a cancelar.'))
        # Tomar motivo/folio de context o usar '02' (errores sin sustitución)
        motivo = (self.env.context.get('cancel_reason') or '02').strip()
        folio_sub = (self.env.context.get('replace_uuid') or False) or None
        self.env['mx.cfdi.engine'].cancel_cfdi(
            origin_model=self._name, origin_id=self.id, uuid=self.cfdi_uuid,
            motivo=motivo, folio_sustitucion=folio_sub
        )
        self.write({'cfdi_state': 'canceled'})
        return True

    def action_create_invoice_and_stamp(self):
        for sale in self:
            if sale.state not in ('confirmed', 'invoiced'):
                raise ValidationError(_('La venta debe estar Confirmada para facturar.'))
    
            # A) Compañías:
            company_invoice = sale.company_id                               # MISMA de la VENTA
            company_fiscal  = sale.empresa_id.res_company_id or company_invoice  # credenciales PAC
    
            tipo   = 'I'  # o el que venga de tu wizard
            uso    = 'G03'
            metodo = sale.metododepago or 'PPD'
            forma  = (sale.formadepago if metodo == 'PUE' else '99') if tipo in ('I', 'E') else None
    
            sale_ctx = sale.with_company(company_invoice).with_context(
                allowed_company_ids=[company_invoice.id, company_fiscal.id]
            )
            move = create_invoice_from_sale(sale_ctx, tipo=tipo, uso_cfdi=uso, metodo=metodo, forma=forma)
            move = move.with_company(company_invoice)
            if move.company_id.id != company_invoice.id:
                move.write({'company_id': company_invoice.id})
            move.action_post()
    
            # C) Conceptos desde la factura (sin impuestos en Importe)
            conceptos = []
            for l in move.invoice_line_ids:
                price = l.price_unit
                qty = l.quantity
                importe = round(price * qty, 2)
    
                iva_ratio = 0.0
                ieps_ratio = 0.0
                for t in l.tax_ids.filtered(lambda t: t.amount_type == 'percent' and t.type_tax_use == 'sale'):
                    try:
                        amt = int(t.amount)
                        if amt == 16:
                            iva_ratio = float(t.amount) / 100.0
                        if amt in (8, 26, 30, 45, 53):
                            ieps_ratio = float(t.amount) / 100.0
                    except Exception:
                        pass
                    
                conceptos.append({
                    'clave_sat': '01010101',
                    'no_identificacion': l.product_id.default_code or str(l.id),
                    'cantidad': qty,
                    'clave_unidad': 'H87',
                    'descripcion': l.name or (l.product_id.display_name or 'Producto'),
                    'valor_unitario': price,
                    'importe': importe,                # SIN impuestos
                    'objeto_imp': '02' if (iva_ratio or ieps_ratio) else '01',
                    'iva': iva_ratio,
                    'ieps': ieps_ratio,
                })
    
            # D) Timbrar usando la compañía FISCAL (solo credenciales), sin cambiar la factura
            engine = self.env['mx.cfdi.engine']\
                        .with_context(allowed_company_ids=[company_invoice.id, company_fiscal.id])\
                        .with_company(company_fiscal)
    
            stamped = engine.generate_and_stamp(
                origin_model='account.move',
                origin_id=move.id,
                tipo=tipo,
                receptor_id=move.partner_id.id,
                uso_cfdi=uso,
                metodo=(metodo if tipo in ('I', 'E') else None),
                forma=(forma if tipo in ('I', 'E') else None),
                conceptos=conceptos,
            )
    
            # E) Enlazar resultado (ya compatibles porque move.company_id == sale.company_id)
            vals = {
                'state': 'invoiced',
                'move_id': move.id,
                'cfdi_state': 'stamped',
                'cfdi_uuid': stamped.get('uuid'),
            }
            if hasattr(move, 'l10n_mx_edi_cfdi_uuid') and stamped.get('uuid'):
                move.l10n_mx_edi_cfdi_uuid = stamped['uuid']
            sale.write(vals)
        return True




    def action_open_invoice(self):
        self.ensure_one()
        if not getattr(self, 'move_id', False):
            raise ValidationError(_('No hay factura vinculada a esta venta.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura'),
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    res_company_cfdi_id = fields.Many2one(
        'res.company', related='empresa_id.res_company_id', string='Compañía fiscal',
        readonly=True
    )

    def action_open_cfdi_company(self):
        self.ensure_one()
        if not self.res_company_cfdi_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Compañía (fiscal)',
            'res_model': 'res.company',
            'view_mode': 'form',
            'res_id': self.res_company_cfdi_id.id,
            'target': 'current',
        }
