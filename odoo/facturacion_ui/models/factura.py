# models/factura.py
# objeto interfaz + líneas + enlaces a origen
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FacturaUI(models.Model):
    _name = 'facturas.factura'
    _description = 'Interfaz de Facturación'
    _inherit = ['mail.thread']
    _order = 'id desc'

    # Encabezado
    empresa_id   = fields.Many2one(
        'empresas.empresa', string='Empresa', required=True, index=True,
        default=lambda s: s.env.user.empresa_actual_id.id
    )

    sucursal_id = fields.Many2one(
        'sucursales.sucursal', string='Sucursal', required=True,
        default=lambda s: s.env.user.sucursal_actual_id.id
    )
    # compañía Odoo (de empresa, si existe; si no, de usuario)
    company_id   = fields.Many2one(
        'res.company', string='Compañía Odoo', required=True, index=True,
        default=lambda s: (s.env.user.empresa_actual_id.company_id.id
                           if s.env.user.empresa_actual_id and s.env.user.empresa_actual_id.company_id
                           else s.env.company.id)
    )
    cliente_id = fields.Many2one('clientes.cliente', string='Cliente', index=True, ondelete='set null')
    tipo         = fields.Selection([('I','Ingresos'),('E','Egresos'),('P','Pago')], default='I', required=True)
    uso_cfdi     = fields.Selection(selection=[('G03','G03'),('S01','S01')], default='G03', string='Uso CFDI')
    metodo       = fields.Selection([('PUE','PUE (Contado)'),('PPD','PPD (Crédito)')], default='PPD', string='Método')
    forma        = fields.Selection(selection=lambda s: s._forma_pago_selection(), string='Forma de pago')
    moneda       = fields.Char(default='MXN')
    serie        = fields.Char()
    folio        = fields.Char()
    fecha        = fields.Datetime(default=fields.Datetime.now)

    # Relación con ventas/cargos elegidos
    venta_ids    = fields.Many2many('ventas.venta', 'fact_ui_sale_rel', 'fact_id', 'sale_id', string='Ventas')
    line_ids     = fields.One2many('facturas.factura.line', 'factura_id', string='Conceptos')

    # CFDI result
    state        = fields.Selection([
        ('draft','Borrador'),
        ('ready','Listo (validado)'),
        ('stamped','Timbrado'),
        ('canceled','Cancelado'),
    ], default='draft', tracking=True)
    uuid         = fields.Char(copy=False, index=True, tracking=True)
    move_id      = fields.Many2one('account.move', string='Factura contable', copy=False)
    attachment_count = fields.Integer(compute='_compute_attachment_count')

    @api.model
    def _forma_pago_selection(self):
        # catálogo mínimo; si tienes modelo de catálogo, puedes poblarlo
        return [('01','Efectivo'),('03','Transferencia'),('04','TDC'),('28','TDD'),('99','Por definir')]

    @api.onchange('empresa_id')
    def _sync_companies(self):
        for r in self:
            if r.empresa_id and r.empresa_id.company_id:
                r.company_id = r.empresa_id.company_id.id
            # coherencia sucursal-empresa
            if r.sucursal_id and r.sucursal_id.empresa != r.empresa_id:
                r.sucursal_id = False

    def _compute_attachment_count(self):
        Att = self.env['ir.attachment']
        for r in self:
            r.attachment_count = Att.search_count([('res_model', '=', r._name), ('res_id', '=', r.id)])

    @api.onchange('sucursal_id')
    def _onchange_sucursal(self):
        for r in self:
            if r.sucursal_id and r.sucursal_id.empresa:
                r.empresa_id = r.sucursal_id.empresa.id

    @api.onchange('metodo','tipo')
    def _onchange_metodo_forma(self):
        """Si es I/E y método PPD, fuerza forma 99; si PUE deja elegir."""
        for r in self:
            if r.tipo in ('I','E'):
                if (r.metodo or '').upper() == 'PPD':
                    r.forma = '99'
            else:
                r.forma = False  # en tipo P no aplica
    # ========= Validaciones clave =========
    def _check_consistency(self):
        self.ensure_one()
        bad = self.line_ids.filtered(lambda l: l.sale_id and l.sale_id.sucursal_id != self.sucursal_id)
        if not self.line_ids:
            raise ValidationError(_('Agrega al menos un concepto a la factura.'))
        if bad:
            raise ValidationError(_('Todas las transacciones deben pertenecer a la sucursal seleccionada.'))

        emp_ids = {l.empresa_id.id for l in self.line_ids if l.empresa_id}
        if len(emp_ids) > 1 or (self.empresa_id and emp_ids and self.empresa_id.id not in emp_ids):
            raise ValidationError(_('Todas las líneas deben pertenecer a la misma empresa.'))
        if self.empresa_id and not emp_ids:
            self.line_ids.write({'empresa_id': self.empresa_id.id})

        # << aquí el cambio >>
        clientes = {l.cliente_id.id for l in self.line_ids if l.cliente_id}
        if len(clientes) > 1:
            raise ValidationError(_('Todas las líneas deben ser del mismo cliente.'))

        if any(l.source_model == 'transacciones.transaccion' and l.sale_state == 'cancelled' for l in self.line_ids):
            raise ValidationError(_('Hay transacciones de ventas canceladas.'))


    # ========= Construcción de la factura contable + timbrado =========
    def action_build_and_stamp(self):
        for r in self:
            # Validación previa súper clara
            if not r.cliente_id and not r.line_ids:
                raise ValidationError(_("Selecciona un cliente en el encabezado o agrega al menos una línea con cliente."))
            r._check_consistency()
            move = r._build_account_move()
            stamped = r._stamp_move_with_engine(move)
            r.write({'state':'stamped', 'uuid': stamped.get('uuid'), 'move_id': move.id})
            r.line_ids._touch_invoice_links(move)


    # ========= Helpers =========
    def _ensure_partner_from_cliente(self, cli):
        """cli: record de clientes.cliente. Devuelve un res.partner (crea si no existe)."""
        Partner = self.env['res.partner']
        Country = self.env['res.country']

        if not cli:
            return Partner.browse(False)

        vat = (getattr(cli, 'rfc', False) or getattr(cli, 'vat', False) or '').strip().upper()
        is_pg = (vat == 'XAXX010101000')

        # Nombre legal (para CFDI 4.0)
        legal = (getattr(cli, 'nombre', False) or cli.display_name or 'CLIENTE').strip().upper()
        if is_pg:
            legal = 'PUBLICO EN GENERAL'

        # Buscar por RFC y luego por nombre
        partner = Partner.search([('vat', '=', vat)], limit=1) if vat else Partner.browse(False)
        if not partner:
            partner = Partner.search([('name', '=', legal)], limit=1)

        # Datos de dirección/regímen
        zip_code = (getattr(cli, 'codigop', False) or getattr(cli, 'zip', False) or '').strip()
        regimen_code = None
        reg = getattr(cli, 'regimen', False)
        if reg and getattr(reg, 'code', False):
            regimen_code = reg.code
        else:
            regimen_code = (getattr(cli, 'regimen_fiscal', False) or '').strip()

        # Para Público en General, usa valores obligatorios estándar
        if is_pg:
            zip_code = '99999'
            regimen_code = '616'  # Sin obligaciones fiscales

        if not partner:
            vals = {
                'name': legal,
            }
            if vat:
                vals['vat'] = vat
            mx = Country.search([('code', '=', 'MX')], limit=1)
            if mx:
                vals['country_id'] = mx.id
            if zip_code:
                vals['zip'] = zip_code
            if 'l10n_mx_edi_legal_name' in Partner._fields:
                vals['l10n_mx_edi_legal_name'] = legal
            if regimen_code and 'l10n_mx_edi_fiscal_regime' in Partner._fields:
                vals['l10n_mx_edi_fiscal_regime'] = regimen_code
            partner = Partner.create(vals)
        else:
            updates = {}
            if vat and not partner.vat:
                updates['vat'] = vat
            if 'l10n_mx_edi_legal_name' in Partner._fields and not getattr(partner, 'l10n_mx_edi_legal_name', False):
                updates['l10n_mx_edi_legal_name'] = legal
            if is_pg:
                if partner.name != 'PUBLICO EN GENERAL':
                    updates['name'] = 'PUBLICO EN GENERAL'
                if partner.zip != '99999':
                    updates['zip'] = '99999'
                if 'l10n_mx_edi_fiscal_regime' in Partner._fields and getattr(partner, 'l10n_mx_edi_fiscal_regime', None) != '616':
                    updates['l10n_mx_edi_fiscal_regime'] = '616'
            else:
                if zip_code and not partner.zip:
                    updates['zip'] = zip_code
                if regimen_code and 'l10n_mx_edi_fiscal_regime' in Partner._fields and not getattr(partner, 'l10n_mx_edi_fiscal_regime', False):
                    updates['l10n_mx_edi_fiscal_regime'] = regimen_code
            if updates:
                partner.write(updates)

        return partner



    def _partner_from_context(self):
        # prioriza el del encabezado; si no, toma de líneas
        if self.cliente_id:
            return self._ensure_partner_from_cliente(self.cliente_id)
        for l in self.line_ids:
            if l.cliente_id:
                return self._ensure_partner_from_cliente(l.cliente_id)
        return False

    def _build_account_move(self):
        """Crea account.move (out_invoice / out_refund). NO timbra todavía."""
        self.ensure_one()
        partner = self._partner_from_context()
        if not partner:
            raise ValidationError(_('Falta cliente.'))

        # Para PPD y tipo I/E: forma = 99 si no viene
        forma = self.forma
        if self.tipo in ('I','E') and (self.metodo or '').upper() == 'PPD' and not forma:
            forma = '99'

        # Mapea líneas UI -> comandos de invoice_line_ids
        lines_cmd = self.with_context(allowed_company_ids=[self.company_id.id])\
                    .line_ids._to_move_line_cmds(self.company_id)

        move_type = 'out_invoice' if self.tipo == 'I' else 'out_refund'
        Move = self.env['account.move'].with_company(self.company_id)
        mxn = self.env.ref('base.MXN', raise_if_not_found=False)
        move = Move.create({
            'move_type': move_type,
            'partner_id': partner.id,
            'company_id': self.company_id.id,
            'currency_id': (mxn.id if mxn else self.company_id.currency_id.id),
            'invoice_origin': self.display_name,
            'invoice_date': fields.Date.context_today(self),
            'invoice_line_ids': lines_cmd,
        })
        move.action_post()

        # Mapea campos EDI básicos si existen (reutiliza tu bridge si quieres)
        try:
            from ..services.mapper import map_mx_edi_fields
            map_mx_edi_fields(move, uso=self.uso_cfdi, metodo=self.metodo, forma=forma)
        except Exception:
            pass
        return move

    def _stamp_move_with_engine(self, move):
        company_invoice = move.company_id
        company_fiscal  = self.empresa_id.res_company_id or company_invoice
        engine = self.env['mx.cfdi.engine']\
                    .with_context(allowed_company_ids=[company_invoice.id, company_fiscal.id])\
                    .with_company(company_fiscal)

        conceptos = self.line_ids._to_cfdi_conceptos()

        # === Información Global para Público en General (CFDI 4.0) ===
        extras = {}
        rec = move.partner_id
        if (self.tipo in ('I', 'E')
            and (rec.vat or '').upper() == 'XAXX010101000'
            and (rec.name or '').strip().upper() == 'PUBLICO EN GENERAL'):
            # Periodicidad: '05' Mensual (ajústala si necesitas diaria/semanal)
            dt = fields.Datetime.context_timestamp(self, self.fecha or fields.Datetime.now())
            extras['informacion_global'] = {
                'periodicidad': '05',             # 01:Diaria, 02:Semanal, 03:Decenal, 04:Quincenal, 05:Mensual, 06:Bimestral
                'meses': f"{dt.month:02d}",       # c_Meses (01..12)
                'anio': str(dt.year),             # AAAA
            }

        return engine.generate_and_stamp(
            origin_model='account.move',
            origin_id=move.id,
            tipo=self.tipo,
            receptor_id=move.partner_id.id,
            uso_cfdi=self.uso_cfdi,
            metodo=(self.metodo if self.tipo in ('I','E') else None),
            forma=(self.forma if self.tipo in ('I','E') else None),
            conceptos=conceptos,
            serie=self.serie, folio=self.folio,
            extras=extras or None,               # ⬅️ aquí pasamos la info global cuando aplique
        )


    # Botón futuro (Complemento de pago)
    def action_build_payment_cfdi(self):
        self.ensure_one()
        raise ValidationError(_('Complemento de pago (tipo P) pendiente de implementar.'))
    
    def action_open_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Adjuntos',
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', self._name), ('res_id', 'in', self.ids)],
            'context': {'default_res_model': self._name, 'default_res_id': self.id},
            'target': 'current',
        }

    def action_placeholder_interest(self):
        self.ensure_one()
        raise ValidationError(_('Intereses: pendiente de implementar.'))
    
    def action_close_form(self):
        # Cierra la vista actual
        return {'type': 'ir.actions.act_window_close'}
    
    def action_prepare_credit_note(self):
        """Placeholder ultra simple: cambia tipo a 'E' (egreso)."""
        self.write({'tipo': 'E'})
        return True

# models/factura.py (continúa)
class FacturaUILine(models.Model):
    _name = 'facturas.factura.line'
    _description = 'Concepto a facturar (UI)'

    _sql_constraints = [
        ('uniq_tx_per_fact', 'unique(factura_id, transaccion_id)',
         'La misma transacción no puede agregarse dos veces a la misma factura.')
    ]

    factura_id  = fields.Many2one('facturas.factura', required=True, ondelete='cascade')
    empresa_id  = fields.Many2one('empresas.empresa', required=True, index=True)
    cliente_id = fields.Many2one('clientes.cliente', required=True, index=True, ondelete='restrict')


    # Tipos de origen
    line_type   = fields.Selection([('sale','Venta'), ('charge','Cargo'), ('interest','Interés')], required=True)
    source_model= fields.Char()   # 'transacciones.transaccion' | 'cargosdetail.cargodetail' | ...
    source_id   = fields.Integer()
    sale_id     = fields.Many2one('ventas.venta', string='Venta')
    sale_state  = fields.Selection(related='sale_id.state')

    # Producto/valores
    producto_id = fields.Many2one('productos.producto', string='Producto/Servicio', required=True, index=True)
    descripcion = fields.Char(required=True)
    cantidad    = fields.Float(default=1.0)
    precio      = fields.Float(default=0.0)
    subtotal    = fields.Float(compute='_calc_totals', store=True)
    iva_ratio   = fields.Float(string='IVA %', default=0.0)
    ieps_ratio  = fields.Float(string='IEPS %', default=0.0)
    iva_amount  = fields.Float(compute='_calc_totals', store=True)
    ieps_amount = fields.Float(compute='_calc_totals', store=True)
    total       = fields.Float(compute='_calc_totals', store=True)

    # Seguimiento de facturación por transacción
    transaccion_id = fields.Many2one('transacciones.transaccion', string='Transacción (si aplica)')
    qty_to_invoice = fields.Float(default=0.0)  # para parciales
    qty_invoiced   = fields.Float(default=0.0)

    @api.depends('cantidad','precio','iva_ratio','ieps_ratio')
    def _calc_totals(self):
        for l in self:
            base = (l.cantidad or 0.0) * (l.precio or 0.0)
            l.subtotal = base
            l.iva_amount = round(base * (l.iva_ratio or 0.0), 2)
            l.ieps_amount = round(base * (l.ieps_ratio or 0.0), 2)
            l.total = round(base + l.iva_amount + l.ieps_amount, 2)

    # ===== Mappers hacia account.move y CFDI =====
    def _to_move_line_cmds(self, company):
        """Devuelve comandos (0,0,vals) para account.move.invoice_line_ids."""
        cmds = []
        Tax = self.env['account.tax']\
              .with_company(company)\
              .with_context(allowed_company_ids=[company.id])
        def _find_tax(percent):
            # percent: 16.0, 8.0, etc.
            dom = [
                ('type_tax_use', '=', 'sale'),
                ('amount_type', '=', 'percent'),
                ('amount', '=', round(percent, 2)),
                ('active', '=', True),
            ]
            if 'company_id' in Tax._fields:
                dom.append(('company_id', '=', company.id))  # ⬅️ evita “de otra empresa”
            return Tax.search(dom, limit=1)

        for l in self:
            taxes = []
            if l.iva_ratio:
                t = _find_tax(l.iva_ratio * 100.0)
                if t:
                    taxes.append(t.id)
            if l.ieps_ratio:
                t = _find_tax(l.ieps_ratio * 100.0)
                if t:
                    taxes.append(t.id)

            vals = {
                'name': l.descripcion or (l.producto_id.display_name or 'Producto'),
                'product_id': (getattr(l.producto_id, 'product_id', False) and l.producto_id.product_id.id) or False,
                'quantity': l.cantidad,
                'price_unit': l.precio,
                'tax_ids': [(6, 0, taxes)] if taxes else False,
            }
            cmds.append((0, 0, vals))
        return cmds

    def _to_cfdi_conceptos(self):
        conceptos = []
        for l in self:
            conceptos.append({
                'clave_sat': getattr(l.producto_id, 'sat_clave_prod_serv', None) or '01010101',
                'clave_unidad': getattr(l.producto_id, 'sat_clave_unidad', None) or 'H87',
                'no_identificacion': getattr(l.producto_id, 'default_code', None) or str(l.producto_id.id),
                'descripcion': l.descripcion or (l.producto_id.display_name or 'Producto'),
                'cantidad': l.cantidad or 1.0,
                'valor_unitario': l.precio or 0.0,
                'importe': round((l.cantidad or 0.0)*(l.precio or 0.0), 2),  # sin impuestos
                'objeto_imp': '02' if (l.iva_ratio or l.ieps_ratio) else '01',
                'iva': float(l.iva_ratio or 0.0),
                'ieps': float(l.ieps_ratio or 0.0),
            })
        return conceptos

    def _touch_invoice_links(self, move):
        """Después de timbrar, registra enlace y vuelve a validar disponible (doble guarda)."""
        EPS = 1e-6
        Link = self.env['ventas.transaccion.invoice.link']
        for l in self.filtered(lambda x: x.transaccion_id):
            tx = l.transaccion_id.sudo().with_for_update()  # “candado” de fila para concurrencia
            qty = l.qty_to_invoice or l.cantidad or 0.0

            # Relee lo ya facturado (links abiertos)
            already = sum(tx.link_ids.filtered(lambda k: k.state != 'canceled').mapped('qty')) or 0.0
            total = tx.cantidad or 0.0
            if already + qty - EPS > total:
                raise ValidationError(_(
                    "Concurrencia: la transacción %s quedó sin disponible al timbrar. "
                    "Disponible: %.4f, intentando facturar: %.4f"
                ) % (tx.display_name, max(total - already, 0.0), qty))

            Link.create({
                'transaccion_id': tx.id,
                'move_id': move.id,
                'qty': qty,
                'state': 'open',
            })
            tx._recompute_invoice_status()

    @api.constrains('transaccion_id', 'cantidad', 'qty_to_invoice')
    def _check_not_exceed_available(self):
        EPS = 1e-6
        for l in self.filtered(lambda x: x.transaccion_id):
            tx = l.transaccion_id.sudo()  # por si
            total = tx.cantidad or 0.0
            already = tx.qty_invoiced or 0.0  # sólo lo timbrado
            this = l.qty_to_invoice or l.cantidad or 0.0
            # Si ya está FULL, no permitir
            if (already + EPS) >= total:
                raise ValidationError(_("La transacción %s ya está completamente facturada.") % tx.display_name)
            if already + this - EPS > total:
                raise ValidationError(_(
                    "Cantidad a facturar (%.4f) excede lo disponible (%.4f) de la transacción %s."
                ) % (this, max(total - already, 0.0), tx.display_name))
    