#ventas/models/venta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date
from odoo import SUPERUSER_ID
import base64
import logging
_logger = logging.getLogger(__name__)

class venta(models.Model):
    _name = 'ventas.venta'
    _description = 'Venta de artículos'
    _check_company_auto = False  # buenas prácticas multiempresa
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'codigo'

    def name_get(self):
        # Mostrar folio (codigo); si algún registro antiguo no tiene codigo, cae a id
        return [(r.id, r.codigo or str(r.id)) for r in self]


    invoice_status2 = fields.Selection([
        ('none', 'No facturada'),
        ('partial', 'Semifacturada'),
        ('full', 'Facturada'),
        ('canceled', 'Cancelada'),
        ('semi_canceled', 'Semi cancelada'),
    ], compute='_compute_agg_status', store=True, default='none', string="Estado de facturación")

    cliente = fields.Many2one('clientes.cliente', string="Cliente", required=True)
    contrato = fields.Many2one('creditos.credito', string="Contrato",
                               domain=lambda self: self._domain_contrato())
                               #domain="[('cliente', '=', cliente), ('status','=','active'), ('vencimiento', '>', context_today())]" if cliente else "[('id', '=', 0)]")

    # Calcula siempre la fecha actual sin depender de otros campos
    hoy = fields.Date(compute='_compute_hoy')


    @api.depends('cliente')
    def _domain_contrato(self):
        if self.cliente:
            return [
                ('cliente', '=', self.cliente.id),
                ('dictamen', '=', 'confirmed'),
                ('vencimiento', '>', fields.Date.context_today(self)),
            ]
        return [('id', '=', 0)]

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

    # Solo conceptos de venta visibles en la vista (excluye DEV/NC/PAGO)
    detalle_venta = fields.One2many(
        'transacciones.transaccion', 'venta_id',
        string="Detalle (Venta)",
        domain=[('tipo', '=', '1')]
    )


    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company, index=True)
    saldo = fields.Float(string="Saldo", readonly=True, store=True, compute="_compute_saldo")
    pagos = fields.Float(string="Pagos", readonly=True, store=True, compute='_add_detalles')

    # Empresa con default por ID
    empresa_id = fields.Many2one(
        'empresas.empresa', string='Empresa', required=True,
        default=lambda self: self.env.user.empresa_actual_id.id,
        #check_company=True, # ⬅️ Entra aquí y valida contra empresas.empresa.company_id
    )

    # Sucursal con default por ID
    sucursal_id = fields.Many2one(
        'sucursales.sucursal', string='Sucursal', required=True,
        default=lambda self: self.env.user.sucursal_actual_id.id,
    )

    @api.onchange('empresa_id')
    def _onchange_empresa_id(self):
        if self.empresa_id:
            comp = getattr(self.empresa_id, 'company_id', False) or getattr(self.empresa_id, 'res_company_id', False)
            if comp:
                self.company_id = comp
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

    res_company_cfdi_id = fields.Many2one(
        'res.company',
        string='Compañía fiscal',
        compute='_compute_res_company_cfdi',
        store=False,
        readonly=True,
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
    @api.depends('empresa_id')
    def _compute_res_company_cfdi(self):
        for r in self:
            comp = False
            emp = r.empresa_id
            if emp:
                # intenta ambos nombres de campo en empresas.empresa
                comp = getattr(emp, 'company_id', False) or getattr(emp, 'res_company_id', False)
            r.res_company_cfdi_id = comp or False
    
    @api.depends('state', 'importe', 'move_id.amount_residual', 'move_id.state', 'move_id.move_type')
    def _compute_saldo(self):
        Move = self.env['account.move']
        for r in self:
            if r.state == 'cancelled':
                r.saldo = 0.0
                continue

            residual = 0.0
            # 1) Si hay move_id y está posteada, úsalo
            if r.move_id and r.move_id.state == 'posted':
                if r.move_id.move_type in ('out_invoice', 'out_refund'):
                    sign = 1.0 if r.move_id.move_type == 'out_invoice' else -1.0
                    residual += sign * (r.move_id.amount_residual or 0.0)

            # 2) Fallback: otras facturas ligadas por origen (parciales), si existen
            if r.codigo:
                others = Move.search([
                    ('state', '=', 'posted'),
                    ('move_type', 'in', ('out_invoice', 'out_refund')),
                    ('invoice_origin', '=', r.codigo),
                    ('company_id', '=', r.company_id.id),
                ])
                for m in others.filtered(lambda m: m.id != (r.move_id.id if r.move_id else 0)):
                    sign = 1.0 if m.move_type == 'out_invoice' else -1.0
                    residual += sign * (m.amount_residual or 0.0)

            # 3) Sin factura: saldo = importe si la venta está confirmada; si no, 0
            if not residual and r.state == 'confirmed':
                r.saldo = r.importe or 0.0
            else:
                r.saldo = max(residual, 0.0)


    @api.onchange('metododepago')
    def _chgmpago(self):
        for record in self:
            if record.metododepago == 'PPD':
                record.formadepago = '99'
        self._apply_prices_by_method()

    def _apply_prices_by_method(self):
        """Forzar precio de líneas según PUE/PPD solo en líneas de venta."""
        for v in self:
            metodo = v.metododepago or 'PPD'
            lines = v.detalle_venta
            for line in lines:
                if line.producto_id:
                    line.precio = line.producto_id.contado if metodo == 'PUE' else line.producto_id.credito


    @api.depends('detalle_venta.subtotal', 'detalle_venta.iva_amount', 'detalle_venta.ieps_amount', 'detalle_venta.importe', 'detalle_venta.tipo')
    def _add_detalles(self):
        for rec in self:
            # Solo líneas de venta (excluir 6,10,11)
            lines = rec.detalle_venta
            rec.importe = sum(l.subtotal for l in lines)
            rec.iva     = sum(l.iva_amount for l in lines)
            rec.ieps    = sum(l.ieps_amount for l in lines)
            rec.total   = sum(l.importe for l in lines)


    @api.constrains('detalle')
    def _check_detalle_venta(self):
        for record in self:
            # Validar solo líneas de venta (excluir DEV/NC/PAGO)
            lines = record.detalle_venta
            if not lines:
                raise ValidationError(_('No se puede guardar una venta sin al menos un producto.'))
            for linea in lines:
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
            if 'empresa_id' in vals or 'sucursal_id' in vals:
                rec._check_user_company_branch(vals=vals)

            # Si se enlaza una factura posteada, marcar la venta como 'invoiced'
            if vals.get('move_id'):
                mv = self.env['account.move'].browse(vals['move_id'])
                if mv and mv.state == 'posted':
                    vals.setdefault('state', 'invoiced')

        res = super().write(vals)

        # Recalcular saldo de contrato si aplica
        for rec in self:
            if rec.contrato:
                rec.contrato._calc_saldoporventas()
        return res

    @api.model
    def create(self, vals):
        vals.setdefault('empresa_id', self.env.user.empresa_actual_id.id)
        vals.setdefault('sucursal_id', self.env.user.sucursal_actual_id.id)

        if vals.get('empresa_id'):
            emp = self.env['empresas.empresa'].browse(vals['empresa_id'])
            if emp:
                comp = getattr(emp, 'company_id', False) or getattr(emp, 'res_company_id', False)
                if comp:
                    vals['company_id'] = comp.id


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

        motivo = (self.env.context.get('cancel_reason') or '02').strip()
        folio_sub = (self.env.context.get('replace_uuid') or False) or None

        provider = self.env['mx.cfdi.engine']._get_provider().with_context(empresa_id=self.empresa_id.id)
        resp = provider._cancel(self.cfdi_uuid, motivo=motivo, folio_sustitucion=folio_sub)

        # (Opcional) guardar acuse si viene
        if resp and resp.get('acuse'):
            self.env['ir.attachment'].sudo().create({
                'name': f"acuse-cancel-{self.cfdi_uuid}.xml",
                'res_model': self._name,
                'res_id': self.id,
                'type': 'binary',
                'datas': base64.b64encode(resp['acuse']).decode('ascii'),
                'mimetype': 'application/xml',
                'description': _('Acuse de cancelación %s') % self.cfdi_uuid,
            })

        self.write({'cfdi_state': 'canceled'})
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




    def action_fetch_cfdi_from_sw(self):
        """Si ya tengo UUID, bajo el XML desde SW y lo adjunto (venta y factura)."""
        self.ensure_one()
        if not self.cfdi_uuid:
            raise ValidationError(_('No hay UUID en la venta.'))
        provider = self.env['mx.cfdi.engine']._get_provider().with_context(empresa_id=self.empresa_id.id)
        data = provider.download_xml_by_uuid(self.cfdi_uuid, tries=10, delay=1.0)
        if not data or not data.get('xml'):
            raise UserError(_('SW no devolvió XML para el UUID %s.') % self.cfdi_uuid)

        # A) factura
        att_move = self.env['ir.attachment'].sudo().create({
            'name': f"{self.cfdi_uuid}.xml",
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'type': 'binary',
            'datas': base64.b64encode(data['xml']).decode('ascii'),   # <- aquí
            'mimetype': 'application/xml',
            'description': _('CFDI timbrado %s (descargado de SW)') % self.cfdi_uuid,
        })

        # B) copia en venta
        self.env['ir.attachment'].sudo().create({
            'name': f"{self.cfdi_uuid}-venta.xml",
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'datas': base64.b64encode(data['xml']).decode('ascii'),   # <- aquí
            'mimetype': 'application/xml',
            'description': _('CFDI timbrado %s (copia en venta)') % self.cfdi_uuid,
        })

        # C) acuse (si viene)
        if data.get('acuse'):
            self.env['ir.attachment'].sudo().create({
                'name': f"acuse-{self.cfdi_uuid}.xml",
                'res_model': self._name,
                'res_id': self.id,
                'type': 'binary',
                'datas': base64.b64encode(data['acuse']).decode('ascii'),  # <- aquí
                'mimetype': 'application/xml',
                'description': _('Acuse CFDI %s (SW DW)') % self.cfdi_uuid,
            })

        return True

    """def action_open_factura_ui(self):
        ""Abre la Interfaz de Facturas prellenada con esta venta (sin timbrar).""
        self.ensure_one()
        fac = self.env['facturas.factura'].create({
            'empresa_id': self.empresa_id.id,
            #'company_id': self.company_id.id,
            'sucursal_id': self.sucursal_id.id,
            'cliente_id': self.cliente.id,   # tu modelo clientes.cliente
            'tipo': 'I',
            'metodo': self.metododepago or 'PPD',
            'forma': (self.formadepago if (self.metododepago == 'PUE') else '99'),
            'origen_venta_id': self.id,      # ← si tu modelo lo tiene, útil para trazar
            'origen_codigo': self.codigo,    # ← opcional; ayuda a ligar por invoice_origin
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'facturas.factura',
            'res_id': fac.id,
            'view_mode': 'form',
            'target': 'current',
        }
        """
    
    def action_open_factura_ui(self):
        """Abre la Interfaz de Facturas prellenada con esta venta (sin timbrar)."""
        self.ensure_one()
        Factura = self.env['facturas.factura']
        vals = {
            'empresa_id': self.empresa_id.id,
            'sucursal_id': self.sucursal_id.id,
            'cliente_id': self.cliente.id,
            'tipo': 'I',
            'metodo': self.metododepago or 'PPD',
            'forma': (self.formadepago if (self.metododepago == 'PUE') else '99'),
            'venta_ids': self.id,      # ← si tu modelo lo tiene, útil para trazar
            #'origen_codigo': self.codigo,    # ← opcional; ayuda a ligar por invoice_origin
        }
        # Ligar la venta si el modelo lo soporta (usa tu M2M venta_ids)
        if 'venta_ids' in Factura._fields:
            vals['venta_ids'] = [(6, 0, [self.id])]
        # Solo manda campos si existen en el modelo
        if 'company_id' in Factura._fields:
            vals['company_id'] = self.company_id.id
        fac = Factura.create(vals)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'facturas.factura',
            'res_id': fac.id,
            'view_mode': 'form',
            'target': 'current',
        }


    
    @api.depends('detalle', 'detalle.write_date', 'detalle.tipo', 'detalle.cantidad')
    def _compute_agg_status(self):
        """
        Solo considera conceptos que son verdaderas líneas de VENTA (tipo == '1').
        Ignora NC, DEV, PAGO y cualquier otra transacción ajena relacionada.
        """
        EPS = 1e-6
        for v in self:
            # Filtra duro por tipo '1' y cantidades > 0
            sale_lines = v.detalle.filtered(
                lambda t: str(getattr(t, 'tipo', '')) == '1' and float(getattr(t, 'cantidad', 0.0) or 0.0) > EPS
            )

            # Log de diagnóstico (ayuda a detectar cuando se cuelan líneas ajenas)
            try:
                _logger.debug(
                    "[ventas.venta:%s] _compute_agg_status -> sale_lines=%s (tipos=%s)",
                    v.id,
                    sale_lines.ids,
                    list({getattr(t, 'tipo', None) for t in v.detalle})
                )
            except Exception:
                pass

            if not sale_lines:
                v.invoice_status2 = 'none'
                continue

            line_states = set()
            for tx in sale_lines:
                st = getattr(tx, 'invoice_status', False)
                if not st:
                    # Fallback por cantidades: qty_invoiced vs cantidad
                    total = float(getattr(tx, 'cantidad', 0.0) or 0.0)
                    inv = float(getattr(tx, 'qty_invoiced', 0.0) or 0.0)
                    if inv <= EPS:
                        st = 'none'
                    elif total > 0.0 and inv + EPS >= total:
                        st = 'full'
                    else:
                        st = 'partial'
                line_states.add(st)

            # Agregación simple
            if line_states == {'canceled'}:
                v.invoice_status2 = 'canceled'
            elif 'canceled' in line_states and (line_states - {'canceled'}):
                v.invoice_status2 = 'semi_canceled'
            elif line_states == {'full'}:
                v.invoice_status2 = 'full'
            elif ('partial' in line_states) or ('full' in line_states and 'none' in line_states):
                v.invoice_status2 = 'partial'
            elif line_states == {'none'}:
                v.invoice_status2 = 'none'
            else:
                v.invoice_status2 = 'partial'


    def action_open_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Adjuntos',
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,tree,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
            'target': 'current',
        }