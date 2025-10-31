# models/factura.py
# objeto interfaz + líneas + enlaces a origen
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
_logger = logging.getLogger(__name__)
import base64
from odoo.osv.expression import OR

class FacturaUI(models.Model):
    _name = 'facturas.factura'
    _description = 'Interfaz de Facturación'
    _inherit = ['mail.thread']
    _order = 'id desc'
    _logger = _logger
    # Encabezado
    empresa_id   = fields.Many2one(
        'empresas.empresa', string='Empresa', required=True, index=True,
        default=lambda s: s.env.user.empresa_actual_id.id
    )
    sucursal_id = fields.Many2one(
        'sucursales.sucursal', string='Sucursal', required=True,
        default=lambda s: s.env.user.sucursal_actual_id.id
    )
    cliente_id = fields.Many2one('clientes.cliente', string='Cliente', index=True, ondelete='set null')
    tipo         = fields.Selection([('I','Ingresos'),('E','Egresos'),('P','Pago')], default='I', required=True)
    egreso_tipo = fields.Selection(
        [('nc', 'Nota de crédito'), ('dev', 'Devolución')],
        string='Tipo de egreso',
        default='nc'
    )
    uso_cfdi = fields.Selection(
        [('G01','G01 - Adquisición de mercancías'),('G02', 'G02 - Devoluciones, descuentos o bonificaciones'),('G03','G03 - Gastos en general'),
         ('S01','S01 - Sin efectos fiscales'),('CP01','CP01 - Pagos'),('CN01','CN01 - Nómina'),
         ('I01','I01 Construcciones'),('I02','I02 - Mobiliario y equipo de oficina para inversiones'),('I03','I03 - Equipo de transporte'), ('I04','I04 - Equipo de computo y accesorios'),
         ('I05','I05 - Dados, troqueles, moldes, matrices y herramientas'),('I06','I06 - Comunicaciones telefónicas'),('I07','I07 - Comunicaciones satelitales'),('I08','I08 - Otra maquinaria y equipo'),('D01','D01 - Honorarios médicos, dentales y gastos hospitalarios'),
         ('D02','D02 - Gastos médicos por incapacidad o discapacidad'),('D03','D03 - Gastos funerales'),('D04','D04 - Donativos'),('D05','D05 - Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación)'),
         ('D06','D06 - Aportaciones voluntarias al SAR'),('D07','D07 - Primas por seguros de gastos médicos'),('D08','D08 - Gastos de transportación escolar obligatoria'),('D09','D09 - Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones'),
         ('D10','D10 - Pagos por servicios educativos (colegiaturas)'),
         ],
        string='Uso CFDI',
        default=False
    )
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
    currency_id = fields.Many2one('res.currency', compute='_compute_currency', store=True, readonly=True)
    # === Pago (tipo P) ===
    pago_importe = fields.Monetary(string='Importe del pago', currency_field='currency_id', default=0.0)


    def _precheck_stock(self):
        Stock = self.env['stock.sucursal.producto'].sudo()
        faltantes = []
        for l in self.line_ids:
            if not l.producto_id or self._is_service_line(l):
                continue
            disp = Stock.get_available(self.sucursal_id, l.producto_id)
            if (l.cantidad or 0.0) > disp + 1e-6:
                faltantes.append(f"- {l.producto_id.display_name}: req={l.cantidad:.4f} disp={disp:.4f}")
        if faltantes:
            raise ValidationError(_("Stock insuficiente:\n%s") % "\n".join(faltantes))


    # Crea y publica el account.move (factura/refund) en la compañía técnica indicada por parámetro
    # 'facturacion_ui.technical_company_id'. Mapea impuestos/productos, enlaza NC con origen y
    # (si está disponible) setea l10n_mx_edi_origin con TipoRelación|UUID. Devuelve el move.
    def _build_account_move(self):
        partner = self._partner_from_context()
        if not partner:
            raise ValidationError(_("Selecciona un cliente en el encabezado o agrega al menos una línea con cliente."))

        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        tech_company_id = int(ICP.get_param('facturacion_ui.technical_company_id', '0') or 0)
        if not tech_company_id:
            raise ValidationError(_("Configura el parámetro del sistema 'facturacion_ui.technical_company_id' con la compañía contable técnica."))
        inv_company = self.env['res.company'].browse(tech_company_id)
                   # ← crear el move en la fiscal
        lines_cmd = self.with_context(allowed_company_ids=[inv_company.id])\
                        .line_ids._to_move_line_cmds(inv_company)
    
        Move = self.env['account.move']\
            .with_company(inv_company)\
            .with_context(allowed_company_ids=[inv_company.id])

        mxn = self.env.ref('base.MXN', raise_if_not_found=False)
        cur_id = inv_company.currency_id.id
        # Si MXN existe y está activa, úsala; si no, conserva la de la compañía
        if mxn and mxn.exists() and getattr(mxn, 'active', True):
            cur_id = mxn.id

        # Asegurar invoice_origin correcto
        origin_codes = []
        if self.tipo == 'E' and self.origin_factura_id:
            # Usar folios de venta de la factura ORIGEN (aunque las líneas del egreso no traigan sale_id)
            if self.origin_factura_id.venta_ids:
                origin_codes = [v.codigo for v in self.origin_factura_id.venta_ids if v.codigo]
            else:
                origin_codes = list({
                    l.sale_id.codigo
                    for l in self.origin_factura_id.line_ids
                    if l.sale_id and l.sale_id.codigo
                })
        else:
            if self.venta_ids:
                origin_codes = [v.codigo for v in self.venta_ids if v.codigo]
            else:
                origin_codes = list({
                    l.sale_id.codigo
                    for l in self.line_ids
                    if l.sale_id and l.sale_id.codigo
                })

        invoice_origin = ' '.join(origin_codes) if origin_codes else (self.display_name or (f"FacturaUI {self.id}"))


        move = Move.create({
            'move_type': 'out_invoice' if self.tipo == 'I' else 'out_refund',
            'partner_id': partner.id,
            'company_id': inv_company.id,
            'currency_id': cur_id,
            'invoice_origin': invoice_origin,
            'invoice_date': fields.Date.context_today(self),
            'invoice_line_ids': lines_cmd,
        })
        move.action_post()
        self._logger.info(
            "CFDI FLOW | MOVE CREATED | fact_id=%s move_id=%s name=%s company=%s lines=%s origin=%s",
            self.id, move.id, getattr(move, 'name', None), move.company_id.id,
            len(move.invoice_line_ids), getattr(move, 'invoice_origin', None)
        )


        # Enlazar NC con factura origen + relación SAT 01 (nota de crédito)
        if self.tipo == 'E' and self.origin_factura_id and self.origin_factura_id.move_id:
            try:
                move.write({'reversed_entry_id': self.origin_factura_id.move_id.id})
            except Exception:
                pass
            # Campo de localización MX que establece TipoRelación|UUID
            try:
                if 'l10n_mx_edi_origin' in move._fields and (self.origin_factura_id.uuid or '').strip():
                    move.write({'l10n_mx_edi_origin': '01|%s' % self.origin_factura_id.uuid})
            except Exception:
                pass

        try:
            from ..services.mapper import map_mx_edi_fields
            map_mx_edi_fields(move, uso=self.uso_cfdi, metodo=self.metodo, forma=self.forma)

        except Exception:
            pass
        return move
    
    # Onchange: si el tipo es ‘E’ (egreso), fuerza método = PUE (contado).
    # Si el tipo es ‘P’ (pago), método/forma/uso no aplican.
    @api.onchange('tipo')
    def _onchange_tipo_force_pue(self):
        for r in self:
            if r.tipo == 'E':
                r.metodo = 'PUE'
            elif r.tipo == 'P':
                # En Pago no aplica método/uso; la forma SÍ se usa en el nodo Pago
                r.metodo = False
                if not r.forma:
                    r.forma = '03'  # Transferencia, default razonable
                r.uso_cfdi = False



    # Onchange (Egreso con factura origen): fija cliente/método/uso y clona TODAS las líneas
# de la factura origen en la UI para permitir devoluciones parciales (sin source_model).
    @api.onchange('origin_factura_id', 'egreso_tipo')
    def _onchange_origin_prefill_lines(self):
        """
        Al seleccionar factura origen en un Egreso:
        - Setear cliente.
        - Cargar **todos** los conceptos de la factura origen.
        - Dejar las líneas sin source_model para que puedas quitar líneas o ajustar cantidades (devolución parcial).
        """
        for r in self:
            if r.tipo != 'E' or not r.origin_factura_id:
                continue
            if r.state != 'draft':
                continue

            # Forzar método contado en egreso
            r.metodo = 'PUE'
            if not r.uso_cfdi:
                r.uso_cfdi = 'G02'
            # Tomar cliente de la factura origen si procede
            if r.origin_factura_id.cliente_id:
                r.cliente_id = r.origin_factura_id.cliente_id.id

            # Vaciar y prellenar líneas desde la factura origen (UI)
            new_lines = [(5, 0, 0)]
            for ol in r.origin_factura_id.line_ids:
                new_lines.append((0, 0, {
                    'empresa_id':   r.empresa_id.id,
                    'cliente_id':   r.origin_factura_id.cliente_id.id if r.origin_factura_id.cliente_id else False,
                    'line_type':    ol.line_type or 'sale',
                    'producto_id':  ol.producto_id.id,
                    'descripcion':  ol.descripcion,
                    'cantidad':     ol.cantidad,   # podrás ajustar para devolución parcial
                    'precio':       ol.precio,
                    'iva_ratio':    ol.iva_ratio,
                    'ieps_ratio':   ol.ieps_ratio,
                    # sin sale_id / transaccion_id / source_model para permitir edición
                }))
            r.line_ids = new_lines

    @api.onchange('tipo', 'origin_factura_id')
    def _onchange_payment_origin(self):
        for r in self:
            if r.tipo == 'P' and r.origin_factura_id:
                r.cliente_id  = r.origin_factura_id.cliente_id.id
                r.empresa_id  = r.origin_factura_id.empresa_id.id
                r.sucursal_id = r.origin_factura_id.sucursal_id.id
                # En pagos no hay conceptos
                r.line_ids = [(5, 0, 0)]
                # Prefill: importe = saldo actual de la factura origen
                r.pago_importe = max(r.origin_factura_id.saldo or 0.0, 0.0)
                if not r.forma:
                    r.forma = '03'



    # Arma los “conceptos” CFDI desde las líneas UI, calcula extras (p.ej. Información Global
    # para Público en General), asegura locking por empresa y llama al engine con empresa_id
    # del emisor fiscal para timbrar (Version 4.0). Devuelve dict con uuid/attachment/document.

    def _stamp_move_with_engine(self, move):
        """Timbrar obligando el contexto de compañía del emisor fiscal (empresas.empresa)."""
        self.ensure_one()
    
        invoice_company = move.company_id  # solo para log/diagnóstico
    
        # Conceptos CFDI
        conceptos = self.line_ids._to_cfdi_conceptos()
    
        # Extras: Información Global para PÚBLICO EN GENERAL
        rec = move.partner_id
        extras = {}
        if (self.tipo in ('I', 'E')
            and (rec.vat or '').strip().upper() == 'XAXX010101000'
            and (rec.name or '').strip().upper() == 'PUBLICO EN GENERAL'):
            dt = fields.Datetime.context_timestamp(self, self.fecha or fields.Datetime.now())
            extras['informacion_global'] = {
                'periodicidad': '05',
                'meses': f"{dt.month:02d}",
                'anio': str(dt.year),
            }
        self._logger.info(
            "CFDI FLOW | EMISOR | empresa=%s (cp=%s) invoice_company=%s",
            self.empresa_id.display_name, (self.empresa_id.cp or ''), invoice_company.id
        )
        # Serializar por empresa para evitar colisiones
        try:
            self.env.cr.execute("SELECT pg_advisory_xact_lock(%s)", [self.empresa_id.id])
        except Exception:
            pass
        self.env.cr.execute("SET LOCAL lock_timeout TO '30s'")
    
        if self.tipo == 'E' and (self.origin_factura_id and (self.origin_factura_id.uuid or '').strip()):
            extras.setdefault('relaciones', []).append({
                'tipo': '01',           # Nota de crédito
                'uuids': [self.origin_factura_id.uuid],
            })
    
        # Timbrar en el contexto de la compañía EMISOR (no la logueada)
        # + Override opcional del proveedor por CONTEXTO (dummy/sw/nombre-modelo)
        _prov = (self.env.context.get('cfdi_provider') or '').strip().lower()
        if not _prov and str(self.env.context.get('cfdi_dummy', '')).lower() in ('1', 'true', 'yes'):
            _prov = 'dummy'
    
        ctx = {'empresa_id': self.empresa_id.id}
        if _prov:
            if _prov in ('dummy', 'mx.cfdi.engine.provider.dummy'):
                ctx['cfdi_provider'] = 'mx.cfdi.engine.provider.dummy'
            elif _prov in ('sw', 'mx.cfdi.engine.provider.sw'):
                ctx['cfdi_provider'] = 'mx.cfdi.engine.provider.sw'
            else:
                ctx['cfdi_provider'] = _prov  # nombre completo del modelo, si lo pasas así
    
        engine = self.env['mx.cfdi.engine'].with_context(**ctx)

        # Para Egresos: que el engine tome totales desde 'conceptos' (no desde el move negativo)
        origin_model = 'account.move'
        origin_id = move.id
        if self.tipo == 'E':
            origin_model = self._name
            origin_id = self.id

        # (opcional) log de verificación
        try:
            sub = round(sum(c.get('importe', 0.0) for c in conceptos), 2)
            self._logger.info("CFDI FLOW | CHECK | tipo=%s subtotal_conceptos=%.2f move_amount_untaxed=%.2f",
                              self.tipo, sub, getattr(move, 'amount_untaxed', 0.0))
        except Exception:
            pass
        
        return engine.generate_and_stamp(
            origin_model=origin_model,
            origin_id=origin_id,
            empresa_id=self.empresa_id.id,
            tipo=self.tipo,
            receptor_id=rec.id,
            uso_cfdi=self.uso_cfdi,
            metodo=(self.metodo if self.tipo in ('I','E') else None),
            forma=(self.forma if self.tipo in ('I','E') else None),
            conceptos=conceptos,
            serie=(self.serie or None),
            folio=(self.folio or None),
            extras=(extras or None),
        )

    
    def _build_payment_extras(self):
        """Arma el payload para el complemento de pagos 2.0 (totales + pagos + doctos)."""
        self.ensure_one()
        origin = self.origin_factura_id
        saldo_ant = float(max(origin.saldo or 0.0, 0.0))
        monto     = float(self.pago_importe or 0.0)
        saldo_ins = max(saldo_ant - monto, 0.0)

        parc_prev = self.env['facturas.factura'].search_count([
            ('tipo', '=', 'P'),
            ('state', '=', 'stamped'),
            ('origin_factura_id', '=', origin.id),
        ])
        num_parc = int(parc_prev) + 1

        # Totales del complemento (en tu flujo emites un pago por CFDI, así que es el mismo monto)
        totales = {
            'monto_total_pagos': monto,
            # si algún día agregas impuestos en el pago, aquí podrías incluir:
            # 'total_traslados_base_iva16': ...,
            # 'total_traslados_impuesto_iva16': ...,
            # etc.
        }

        pago = {
            'fecha': fields.Datetime.context_timestamp(
                self, self.fecha or fields.Datetime.now()
            ).strftime('%Y-%m-%dT%H:%M:%S'),
            'forma': self.forma or '03',        # SAT FormaDePago del nodo <pago20:Pago>
            'moneda': self.moneda or 'MXN',     # Moneda del pago (MonedaP) — el CFDI sigue siendo XXX
            'monto': monto,
            'docs': [{
                'uuid': (origin.uuid or '').strip(),
                'serie': origin.serie or '',
                'folio': origin.folio or '',
                'num_parcialidad': num_parc,
                'saldo_anterior': saldo_ant,
                'importe_pagado': monto,
                'saldo_insoluto': saldo_ins,
            }],
        }

        # Nota: el engine usará 'pagos_totales' y luego 'pagos' para construir el XML con el orden correcto.
        return {
            'pagos_totales': totales,
            'pagos': [pago],
        }


    def _stamp_payment_with_engine(self):
        """Timbrar complemento de pago SIN crear account.move; origen = esta FacturaUI."""
        self.ensure_one()
        rec = self._partner_from_context()

        # Ajuste de proveedor por contexto (igual que en _stamp_move_with_engine)
        _prov = (self.env.context.get('cfdi_provider') or '').strip().lower()
        if not _prov and str(self.env.context.get('cfdi_dummy', '')).lower() in ('1', 'true', 'yes'):
            _prov = 'dummy'
        ctx = {'empresa_id': self.empresa_id.id}
        if _prov:
            if _prov in ('dummy', 'mx.cfdi.engine.provider.dummy'):
                ctx['cfdi_provider'] = 'mx.cfdi.engine.provider.dummy'
            elif _prov in ('sw', 'mx.cfdi.engine.provider.sw'):
                ctx['cfdi_provider'] = 'mx.cfdi.engine.provider.sw'
            else:
                ctx['cfdi_provider'] = _prov

        engine = self.env['mx.cfdi.engine'].with_context(**ctx)
        extras = self._build_payment_extras()

        return engine.generate_and_stamp(
            origin_model=self._name,
            origin_id=self.id,
            empresa_id=self.empresa_id.id,
            tipo='P',
            receptor_id=rec.id,
            uso_cfdi='CP01',        # <-- EN P es obligatorio CP01 (Uso CFDI)
            metodo=None,            # <-- En CFDI tipo P NO lleva MetodoPago/ FormaPago a nivel Comprobante
            forma=None,
            conceptos=[],
            serie=(self.serie or None),
            folio=(self.folio or None),
            extras=(extras or None),
        )




    # A partir de clientes.cliente crea/actualiza (si es necesario) un res.partner con RFC,
    # nombre legal, CP y régimen fiscal (usa 616/99999 para Público en General). Devuelve partner.
    def _ensure_partner_from_cliente(self, cli):
        """cli: record de clientes.cliente. Devuelve un res.partner (crea si no existe)."""
        Partner = self.env['res.partner']
        Country = self.env['res.country']

        if not cli:
            return Partner.browse(False)

        person = getattr(cli, 'persona_id', False)  # fuente de verdad si los related no están store
        vat = ((getattr(person, 'rfc', False) or '')
               or (getattr(cli, 'rfc', False) or '')
               or (getattr(cli, 'vat', False) or '')).strip().upper()
        is_pg = (vat == 'XAXX010101000')

        # Nombre legal (para CFDI 4.0)
        legal = ((getattr(person, 'name', False) or '')
                 or (getattr(cli, 'nombre', False) or '')
                 or cli.display_name or 'CLIENTE').strip().upper()
        if is_pg:
            legal = 'PUBLICO EN GENERAL'

        # Buscar por RFC y luego por nombre
        partner = Partner.search([('vat', '=', vat)], limit=1) if vat else Partner.browse(False)
        if not partner:
            partner = Partner.search([('name', '=', legal)], limit=1)

        # Datos de dirección/regímen
        zip_code = ((getattr(person, 'codigop', False) or '')
                    or (getattr(cli, 'codigop', False) or '')
                    or (getattr(cli, 'zip', False) or '')).strip()
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

        updates = {}
        created = False
        if not partner or not partner.exists():
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
            elif regimen_code and 'cfdi_regimen_fiscal' in Partner._fields:   
                vals['cfdi_regimen_fiscal'] = regimen_code                    

            partner = Partner.create(vals)
            created = True
        else:
            updates = {}
            if vat and not partner.vat:
                updates['vat'] = vat

            # === Nombre legal ===
            if 'l10n_mx_edi_legal_name' in Partner._fields:
                if (partner.l10n_mx_edi_legal_name or '').strip().upper() != legal:
                    updates['l10n_mx_edi_legal_name'] = legal
            else:
                # Si no existe el campo de localización, asegura que name coincida
                if (partner.name or '').strip().upper() != legal:
                    updates['name'] = legal

            if is_pg:
                if partner.name != 'PUBLICO EN GENERAL':
                    updates['name'] = 'PUBLICO EN GENERAL'
                if partner.zip != '99999':
                    updates['zip'] = '99999'
                if 'l10n_mx_edi_fiscal_regime' in Partner._fields:
                    if getattr(partner, 'l10n_mx_edi_fiscal_regime', None) != '616':
                        updates['l10n_mx_edi_fiscal_regime'] = '616'
                elif 'cfdi_regimen_fiscal' in Partner._fields:
                    if getattr(partner, 'cfdi_regimen_fiscal', None) != '616':
                        updates['cfdi_regimen_fiscal'] = '616'
            else:
                if zip_code and not partner.zip:
                    updates['zip'] = zip_code

                # === Régimen fiscal: acepta cualquiera de los dos campos ===
                if regimen_code:
                    if 'l10n_mx_edi_fiscal_regime' in Partner._fields:
                        if getattr(partner, 'l10n_mx_edi_fiscal_regime', None) != regimen_code:
                            updates['l10n_mx_edi_fiscal_regime'] = regimen_code
                    elif 'cfdi_regimen_fiscal' in Partner._fields:
                        if getattr(partner, 'cfdi_regimen_fiscal', None) != regimen_code:
                            updates['cfdi_regimen_fiscal'] = regimen_code

            if updates:
                partner.write(updates)

        self._logger.info("CFDI FLOW | PARTNER FROM CLIENTE | cliente_id=%s rfc=%s legal=%s zip=%s regimen=%s -> partner_id=%s (created=%s)",
                     cli.id, vat, legal, zip_code, regimen_code, partner.id if partner else None, created)
        if updates:
            self._logger.info("CFDI FLOW | PARTNER UPDATE | partner_id=%s updates=%s", partner.id, updates)

        return partner


    # ============================== utils ==============================

    # Construye y valida la factura UI, genera el account.move en la “compañía técnica”,
    # timbra con el engine CFDI, guarda uuid/estado/enlace al move y registra links de líneas.
    # Publica en el chatter errores si falla.
    def action_build_and_stamp(self):
        for r in self:
            try:
                # Validaciones de negocio
                r._check_consistency()
                self._logger.info(
                    "CFDI FLOW | START | id=%s tipo=%s egreso_tipo=%s empresa=%s sucursal=%s cliente=%s lines=%s total=%.2f saldo=%.2f",
                    r.id, r.tipo, (r.egreso_tipo or ''), (r.empresa_id.id if r.empresa_id else None),
                    (r.sucursal_id.id if r.sucursal_id else None), (r.cliente_id.id if r.cliente_id else None),
                    len(r.line_ids), (r.importe_total or 0.0), (r.saldo or 0.0)
                )

                # Si es Ingreso, valida stock antes de crear el move
                if r.tipo == 'I':
                    r._precheck_stock()

                # ====== TIPO P (Complemento de pago) ======
                if r.tipo == 'P':
                    # 1) Registrar efectos internos PRIMERO:
                    #    - Crea la transacción de pago (tipo 11)
                    #    - Descuenta counters en la factura origen
                    #    Si algo falla aquí (parámetro, modelo, permisos), se aborta ANTES de timbrar.
                    r._apply_payment_effects()

                    # 2) Timbrar complemento de pago (sin account.move)
                    stamped = r._stamp_payment_with_engine()
                    self._logger.info("CFDI FLOW | PAYMENT STAMPED | uuid=%s", stamped.get('uuid'))
                    r.write({'state': 'stamped', 'uuid': stamped.get('uuid'), 'move_id': False})

                    # 3) Recomputar saldo en la factura origen y ventas ligadas
                    if r.origin_factura_id:
                        origin = r.origin_factura_id
                        try:
                            origin.write({'state': origin.state})  # no-op para disparar recompute store
                        except Exception:
                            pass
                        ventas_orig = origin.venta_ids | self.env['ventas.venta'].browse(
                            list({l.sale_id.id for l in origin.line_ids if l.sale_id})
                        )
                        if ventas_orig:
                            try:
                                ventas_orig.write({'state': ventas_orig[0].state})  # no-op para @depends
                            except Exception:
                                pass
                    # Listo con P; pasa al siguiente registro
                    continue

                # ====== TIPOS I/E (como ya lo tenías) ======
                move = r._build_account_move()

                stamped = r._stamp_move_with_engine(move)
                self._logger.info("CFDI FLOW | STAMPED | uuid=%s", stamped.get('uuid'))
                r.write({'state': 'stamped', 'uuid': stamped.get('uuid'), 'move_id': move.id})
                r.line_ids._touch_invoice_links(move)

                if r.tipo == 'I':
                    # stock en ingresos
                    try:
                        r._apply_stock_on_ingreso()
                    except Exception as _e:
                        self._logger.warning("STOCK | no se pudo descontar en ingreso: %s", _e)


                if r.tipo in ('I', 'E'):
                    mv_cur = r.currency_id or r.env.company.currency_id
                    if mv_cur and hasattr(mv_cur, 'active') and not mv_cur.active:
                        try:
                            inv_company = r._resolve_inv_company()
                            r.message_post(body=_(
                                "Advertencia: la moneda configurada (%s) está INACTIVA; se usará la moneda activa de la compañía contable (%s)."
                            ) % ((mv_cur.name or mv_cur.display_name or '??'),
                                 (inv_company.currency_id.name or '??')))
                        except Exception:
                            pass


                # === Efectos post-timbrado por tipo ===
                if r.tipo == 'I':
                    # Inicializa contadores disponibles por línea si no estaban seteados
                    for l in r.line_ids:
                        vals = {}
                        if not l.qty_dev_available:
                            vals['qty_dev_available'] = (l.cantidad or 0.0)
                        if not l.total_dev_available:
                            vals['total_dev_available'] = (l.total or 0.0)
                        if vals:
                            l.write(vals)

                elif r.tipo == 'E' and r.origin_factura_id:
                    # 1) Crear transacciones por cada línea **ANTES** de tocar contadores
                    try:
                        r._create_transactions_for_egreso(move)
                    except Exception as _e:
                        self._logger.warning("DEV/NC tx | error: %s", _e)
                    # 2) Stock (solo DEV)
                    if (r.egreso_tipo or '') == 'dev':
                        try:
                            r._return_devolucion_to_stock()
                        except Exception as _e:
                            self._logger.warning("DEV STOCK | no se pudo ajustar stock: %s", _e)
                    # 3) Descontar contadores en la factura origen
                    try:
                        r._apply_credit_counters_on_origin()
                    except Exception as _e:
                        self._logger.warning("DEV/NC counters | error: %s", _e)

                # === Actualizar Ventas relacionadas: estado -> 'invoiced' y, si es una sola, ligar move ===
                ventas_from_lines = self.env['ventas.venta'].browse(
                    list({l.sale_id.id for l in r.line_ids if l.sale_id})
                )
                ventas = (r.venta_ids | ventas_from_lines).sudo()

                if ventas:
                    vals = {'state': 'invoiced'}
                    # Solo intenta ligar el move si el modelo lo soporta
                    if move.state == 'posted' and len(ventas) == 1 and 'move_id' in ventas._fields:
                        vals['move_id'] = move.id
                    ventas.write(vals)

                # === si es EGRESO, recomputar origen y sus ventas (ya lo tenías)
                if r.tipo == 'E' and r.origin_factura_id:
                    origin = r.origin_factura_id
                    try:
                        origin.write({'state': origin.state})  # no-op para recompute store
                    except Exception:
                        pass
                    ventas_orig = origin.venta_ids | self.env['ventas.venta'].browse(
                        list({l.sale_id.id for l in origin.line_ids if l.sale_id})
                    )
                    if ventas_orig:
                        try:
                            ventas_orig.write({'state': ventas_orig[0].state})
                        except Exception:
                            pass
                self._logger.info(
                    "CFDI FLOW | DONE | id=%s tipo=%s state=%s uuid=%s move_id=%s",
                    r.id, r.tipo, r.state, (r.uuid or ''), (r.move_id.id if r.move_id else None)
                )

            except Exception as e:
                self._logger.exception("CFDI FLOW | ERROR | fact_id=%s", r.id)
                try:
                    r.message_post(body="CFDI ERROR:<br/>%s" % (str(e) or repr(e)), subtype_xmlid="mail.mt_note")
                except Exception:
                    pass
                raise
        try:
            r.message_post(body=_("Timbrado OK. UUID: %s") % (r.uuid or ''), subtype_xmlid="mail.mt_note")
        except Exception:
            pass



    # === Helpers post-operación ===
    # R<esolver compañía contable destino ===
    def _resolve_inv_company(self):
        ICP = self.env['ir.config_parameter'].sudo()
        cid = int(ICP.get_param('facturacion_ui.technical_company_id', '0') or 0)
        if cid:
            c = self.env['res.company'].browse(cid)
            if c and c.exists():
                return c

        # Fallbacks desde empresas.empresa → res.company
        emp = self.empresa_id
        for fname in ('res_company_id', 'company_id', 'company'):
            c = getattr(emp, fname, False)
            if c and getattr(c, '_name', '') == 'res.company':
                return c

        # Último recurso: compañía actual del entorno
        return self.env.company


    def _return_devolucion_to_stock(self):
        """Regresa a stock las cantidades devueltas (por sucursal) usando stock.sucursal.producto."""
        self.ensure_one()
        if (self.egreso_tipo or '') != 'dev':
            return
        Stock = self.env['stock.sucursal.producto'].sudo()
        tot = 0.0
        for l in self.line_ids:
            if not l.producto_id or self._is_service_line(l):
                continue
            qty = l.cantidad or 0.0
            if qty > 0:
                Stock.add_stock(self.sucursal_id, l.producto_id, qty)
                tot += qty
        self._logger.info(
            "STOCK | IN (DEV) | fact_id=%s sucursal=%s total_qty=%.4f",
            self.id, (self.sucursal_id.id if self.sucursal_id else None), tot
        )

                


    def _apply_credit_counters_on_origin(self):
        """Descuenta contadores en líneas de la factura origen según egreso_tipo."""
        self.ensure_one()
        origin = self.origin_factura_id
        if not origin:
            return
        if (self.egreso_tipo or '') == 'dev':
            # Descontar cantidades por producto (consume de líneas del origen en orden)
            pend_by_prod = {}
            for l in self.line_ids:
                if l.producto_id:
                    pend_by_prod[l.producto_id.id] = pend_by_prod.get(l.producto_id.id, 0.0) + (l.cantidad or 0.0)
            for ol in origin.line_ids.sorted('id'):
                pid = ol.producto_id.id if ol.producto_id else False
                if not pid:
                    continue
                pend = pend_by_prod.get(pid, 0.0)
                if pend <= 0:
                    continue
                take = min(ol.qty_dev_available or 0.0, pend)
                if take > 0:
                    # Reducir cantidad disponible y proporcionalmente su total acreditable
                    new_qty = max((ol.qty_dev_available or 0.0) - take, 0.0)
                    ratio = 0.0
                    if (ol.cantidad or 0.0) > 1e-9:
                        ratio = take / (ol.cantidad or 1.0)
                    new_total_av = max((ol.total_dev_available or 0.0) - (ol.total or 0.0) * ratio, 0.0)
                    ol.write({'qty_dev_available': new_qty, 'total_dev_available': new_total_av})
                    pend_by_prod[pid] = pend - take

        elif (self.egreso_tipo or '') == 'nc':
            # Descontar del total acreditable (sin tocar cantidades)
            pend = sum((l.total or 0.0) for l in self.line_ids)
            for ol in origin.line_ids.sorted('id'):
                if pend <= 1e-9:
                    break
                take = min(ol.total_dev_available or 0.0, pend)
                if take > 0:
                    new_total_av = max((ol.total_dev_available or 0.0) - take, 0.0)
                    ol.write({'total_dev_available': new_total_av})
                    pend -= take
    

    def _create_transactions_for_egreso(self, move):
        """Crea transacciones por cada línea del EGRESO.
           DEV (devolución): tipo '6' (Entrada lógica).
           NC (nota de crédito): tipo '10' (Sin efecto de stock).
           Importante: NO usar cliente_id (ese campo no existe en transacciones.transaccion).
        """
        self.ensure_one()
        if not self.origin_factura_id:
            return
        
        token = self._own_ref_token()
        created = 0
        used_fallback = False
        dev_count = 0
        nc_count  = 0

        try:
            Tx = self.env['transacciones.transaccion'].sudo()
        except KeyError:
            self._logger.warning("EGRESO TX | modelo 'transacciones.transaccion' no disponible; omitiendo creación.")
            return



        ref = (getattr(move, 'name', False) or (self.uuid or 'EGRESO')).strip()

        token = self._own_ref_token()
        created = 0
        dev_count = 0
        nc_count  = 0
        used_fallback = False

        # RFC helper (si lo tienes en clientes.cliente)
        def _cli_rfc():
            cli = self.cliente_id
            return ((getattr(cli, 'rfc', False) or getattr(cli, 'vat', False) or
                     (getattr(getattr(cli, 'persona_id', False), 'rfc', False) or '')) or '').strip().upper()

        created = 0
        origin = self.origin_factura_id

        # Buckets FIFO por (venta, producto) con disponibles del ORIGEN
        buckets = []
        for ol in origin.line_ids.sorted('id'):
            sale = ol.sale_id
            prod = ol.producto_id
            if not sale:
                continue
            buckets.append({
                'sale': sale,
                'producto': prod,
                'qty_av': float(ol.qty_dev_available or 0.0),   # para DEV
                'amt_av': float(ol.total_dev_available or 0.0), # para NC
            })

        def _fallback_sale():
            if origin.venta_ids:
                return origin.venta_ids[0]
            for ol in origin.line_ids:
                if ol.sale_id:
                    return ol.sale_id
            return False

        rfc = _cli_rfc()
        ref_base = (getattr(move, 'name', False) or (self.uuid or 'EGRESO')).strip()
        ref = f"{self._own_ref_token()} {ref_base}"   # <— token al inicio
        if (self.egreso_tipo or '') == 'dev':
            # Repartir por CANTIDAD (mismo producto)
            for l in self.line_ids:
                if not l.producto_id:
                    continue
                need_qty = float(l.cantidad or 0.0)
                if need_qty <= 0:
                    continue

                # 1) Consumir buckets del mismo producto
                for b in buckets:
                    if need_qty <= 1e-9:
                        break
                    if not b['producto'] or b['producto'].id != l.producto_id.id:
                        continue
                    take = min(need_qty, b['qty_av'])
                    if take <= 1e-9:
                        continue
                    
                    vals = {
                        'fecha': fields.Date.context_today(self),
                        'venta_id': b['sale'].id if b['sale'] else False,
                        'producto_id': l.producto_id.id,
                        'cantidad': -take,                         # negativa → importe negativo
                        'precio': l.precio or 0.0,                 # positivo
                        'referencia': ref,
                        'sucursal_id': self.sucursal_id.id,
                        'tipo': '6',                               # Dev de Cliente (Entrada lógica)
                        # helpers
                        'empresa_id_helper': self.empresa_id.id,
                        'cliente_rfc_helper': rfc or False,
                    }
                    try:
                        Tx.create(vals)
                        created += 1
                        dev_count += 1
                    except Exception as e:
                        self._logger.warning("EGRESO TX | create(dev/1) falló: %s", e)

                    b['qty_av'] -= take
                    need_qty    -= take

                # 2) Si falta, crea 1 transacción ligada a alguna venta del origen
                if need_qty > 1e-9:
                    sale = _fallback_sale()
                    if sale:
                        used_fallback = True
                    vals = {
                        'fecha': fields.Date.context_today(self),
                        'venta_id': sale.id if sale else False,
                        'producto_id': l.producto_id.id,
                        'cantidad': -need_qty,
                        'precio': l.precio or 0.0,
                        'referencia': ref,
                        'sucursal_id': self.sucursal_id.id,
                        'tipo': '6',
                        'empresa_id_helper': self.empresa_id.id,
                        'cliente_rfc_helper': rfc or False,
                    }
                    try:
                        Tx.create(vals)
                        created += 1
                        dev_count += 1
                    except Exception as e:
                        self._logger.warning("EGRESO TX | create(dev/2) falló: %s", e)

        else:
            # Nota de crédito: repartir por IMPORTE, priorizando (venta, producto)
            for l in self.line_ids:
                need_amt = float(l.total or 0.0)
                if need_amt <= 1e-9:
                    continue

                # 1) Buckets de mismo producto
                for b in buckets:
                    if need_amt <= 1e-9:
                        break
                    same_prod = (b['producto'] and l.producto_id and b['producto'].id == l.producto_id.id)
                    if not same_prod:
                        continue

                    take = min(need_amt, b['amt_av'])
                    if take <= 1e-9:
                        continue

                    ratio = (take / (l.total or 1.0))
                    qty_part = (l.cantidad or 0.0) * ratio

                    vals = {
                        'fecha': fields.Date.context_today(self),
                        'venta_id': b['sale'].id if b['sale'] else False,
                        'producto_id': l.producto_id.id,
                        'cantidad': -qty_part,                     # negativa
                        'precio': l.precio or 0.0,
                        'referencia': ref,
                        'sucursal_id': self.sucursal_id.id,
                        'tipo': '10',                              # sin efecto de stock
                        'empresa_id_helper': self.empresa_id.id,
                        'cliente_rfc_helper': rfc or False,
                    }
                    try:
                        Tx.create(vals)
                        created += 1
                        nc_count += 1
                        
                    except Exception as e:
                        self._logger.warning("EGRESO TX | create(nc/1) falló: %s", e)

                    b['amt_av'] -= take
                    need_amt    -= take

                # 2) Consumir cualquier bucket con amt_av
                if need_amt > 1e-9:
                    for b in buckets:
                        if need_amt <= 1e-9:
                            break
                        take = min(need_amt, b['amt_av'])
                        if take <= 1e-9:
                            continue

                        ratio = (take / (l.total or 1.0))
                        qty_part = (l.cantidad or 0.0) * ratio

                        vals = {
                            'fecha': fields.Date.context_today(self),
                            'venta_id': b['sale'].id if b['sale'] else False,
                            'producto_id': l.producto_id.id,
                            'cantidad': -qty_part,
                            'precio': l.precio or 0.0,
                            'referencia': ref,
                            'sucursal_id': self.sucursal_id.id,
                            'tipo': '10',
                            'empresa_id_helper': self.empresa_id.id,
                            'cliente_rfc_helper': rfc or False,
                        }
                        try:
                            Tx.create(vals)
                            created += 1
                            nc_count += 1
                        except Exception as e:
                            self._logger.warning("EGRESO TX | create(nc/2) falló: %s", e)

                        b['amt_av'] -= take
                        need_amt    -= take

                    # 3) Último recurso: una sola ligada a alguna venta
                    if need_amt > 1e-9:
                        sale = _fallback_sale()
                        if sale:
                            used_fallback = True
                        ratio = (need_amt / (l.total or 1.0))
                        qty_part = (l.cantidad or 0.0) * ratio
                        vals = {
                            'fecha': fields.Date.context_today(self),
                            'venta_id': sale.id if sale else False,
                            'producto_id': l.producto_id.id,
                            'cantidad': -qty_part,
                            'precio': l.precio or 0.0,
                            'referencia': ref,
                            'sucursal_id': self.sucursal_id.id,
                            'tipo': '10',
                            'empresa_id_helper': self.empresa_id.id,
                            'cliente_rfc_helper': rfc or False,
                        }
                        try:
                            Tx.create(vals)
                            created += 1
                            nc_count += 1
                        except Exception as e:
                            self._logger.warning("EGRESO TX | create(nc/3) falló: %s", e)

        # Asegura escritura en DB antes de continuar
        try:
            Tx.flush()
        except Exception:
            pass

        self._logger.info(
            "EGRESO TX | creadas=%s dev=%s nc=%s fallback=%s ref=%s egreso_tipo=%s",
            created, dev_count, nc_count, used_fallback, ref, (self.egreso_tipo or 'nc')
        )


    def _get_payment_product(self, strict=False):
        """
        Devuelve el producto de pago configurado en el parámetro del sistema
        'facturacion_ui.payment_product_id'. En modo estricto, exige que el parámetro
        exista y apunte a un producto válido (sin hacer búsquedas ni autocorrecciones).
        """
        ICP = self.env['ir.config_parameter'].sudo()
        raw = (ICP.get_param('facturacion_ui.payment_product_id', '') or '').strip()
        pid = int(raw) if raw.isdigit() else 0
        p = self.env['productos.producto'].browse(pid) if pid else False
        if p and p.exists():
            return p

        if strict:
            raise ValidationError(_("Configura el parámetro del sistema 'facturacion_ui.payment_product_id' con el ID de un producto válido para registrar la transacción del complemento de pago."))

        # --- Modo no estricto (fallback legacy): intenta localizar por nombre y autoajustar parámetro ---
        p = self.env['productos.producto'].search([('name', 'ilike', 'pago')], limit=1)
        if not p:
            raise ValidationError(_("Configura el parámetro 'facturacion_ui.payment_product_id' o crea un producto llamado 'Pago' sin impuestos."))
        ICP.set_param('facturacion_ui.payment_product_id', str(p.id))
        return p


    def _apply_payment_effects(self):
        """Crea transacción (una) de pago sin producto de la factura original y descuenta crédito."""
        self.ensure_one()
        origin = self.origin_factura_id
        if not origin:
            return
        ref_base = (getattr(self.origin_factura_id.move_id, 'name', self.origin_factura_id.display_name or '') or '')
        referencia = f"{self._own_ref_token()} Pago a factura {ref_base}"

        # 👇 Forma robusta: intenta obtener el modelo y captura KeyError si no existe
        try:
            Tx = self.env['transacciones.transaccion'].sudo()
        except KeyError:
            raise ValidationError(_("No está disponible el modelo 'transacciones.transaccion'; no se puede registrar la transacción de pago."))

    
        if (self.pago_importe or 0.0) > 0.0:
            pago_prod = self._get_payment_product(strict=True)
    
            # elegir alguna venta del origen
            venta = origin.venta_ids[:1] and origin.venta_ids[0] or False
            if not venta:
                for ol in origin.line_ids:
                    if ol.sale_id:
                        venta = ol.sale_id
                        break
            vals = {
                'fecha': fields.Date.context_today(self),
                'venta_id': venta.id if venta else False,
                'producto_id': pago_prod.id,
                'cantidad': 1.0,
                'precio': -(self.pago_importe or 0.0),
                'referencia': referencia,
                'sucursal_id': (venta.sucursal_id.id if venta else origin.sucursal_id.id),
                'tipo': '11',  # sin efecto de stock
                'empresa_id_helper': self.empresa_id.id,
                'cliente_rfc_helper': (getattr(self.cliente_id, 'rfc', False) or getattr(self.cliente_id, 'vat', False) or '') or False,
            }
            tx_rec = Tx.create(vals)
    
            # Asegura escritura inmediata
            try:
                self.env['transacciones.transaccion'].flush()
            except Exception:
                pass
            
            self._logger.info(
                "PAGO | transacción creada id=%s, venta_id=%s, sucursal_id=%s, importe=%.2f",
                getattr(tx_rec, 'id', None),
                (venta.id if venta else None),
                (venta.sucursal_id.id if venta else origin.sucursal_id.id),
                -(self.pago_importe or 0.0),
            )

        # Descontar del total acreditable del origen (como NC global)
        pend = (self.pago_importe or 0.0)
        for ol in origin.line_ids.sorted('id'):
            if pend <= 1e-9:
                break
            take = min(ol.total_dev_available or 0.0, pend)
            if take > 1e-9:
                ol.write({'total_dev_available': max((ol.total_dev_available or 0.0) - take, 0.0)})
                pend -= take

        self._logger.info(
            "PAGO | counters | fact_origen=%s importe=%.2f counters_restados_ok",
            (origin.id if origin else None), (self.pago_importe or 0.0)
        )




    
    # Devuelve el catálogo mínimo de formas de pago para el campo 'forma' en la UI.
    @api.model
    def _forma_pago_selection(self):
        # catálogo mínimo; si tienes modelo de catálogo, puedes poblarlo
        return [('01','Efectivo'),('03','Transferencia'),('04','Tarjeta de crédito'),('28','Tarjeta de débito'),('99','Por definir'),
                ('02','Cheque nominativo'),('05','Monedero electrónico'),('06','Dinero electrónico'),
                ('08','Vales de despensa'),('12','Dación en pago'),('13','Pago por subrogación'),
                ('14','Pago por consignación'),('15','Condonación'),('17','Compensación'),
                ('23','Novación'),('24','Confusión'),('25','Remisión de deuda'),
                ('26','Prescripción o caducidad'),('27','A satisfacción del acreedor'),
                ('29','Tarjeta de servicios'),('30','Aplicación de anticipos')
                ]

    # Onchange: si la sucursal elegida pertenece a otra empresa, limpia el campo sucursal.
    @api.onchange('empresa_id')
    def _sync_companies(self):
        for r in self:
            if r.sucursal_id and r.sucursal_id.empresa != r.empresa_id:
                r.sucursal_id = False

    # Onchange: al cambiar la sucursal, sincroniza automáticamente la empresa del encabezado.
    @api.onchange('sucursal_id')
    def _onchange_sucursal(self):
        for r in self:
            if r.sucursal_id and r.sucursal_id.empresa:
                r.empresa_id = r.sucursal_id.empresa.id

    # Onchange: en I/E, si método = PPD fuerza forma = '99'; para tipo P limpia la forma (no aplica).
    @api.onchange('metodo','tipo')
    def _onchange_metodo_forma(self):
        """Si es I/E y método PPD, fuerza forma 99; en Pago permite forma (default 03)."""
        for r in self:
            if r.tipo in ('I','E'):
                if (r.metodo or '').upper() == 'PPD':
                    r.forma = '99'
            elif r.tipo == 'P':
                if not r.forma:
                    r.forma = '03'


    # Obtiene el res.partner a usar: prioriza cliente del encabezado y, si no, toma el de la
    # primera línea con cliente, normalizándolo con _ensure_partner_from_cliente().
    def _partner_from_context(self):
        # prioriza el del encabezado; si no, toma de líneas
        if self.cliente_id:
            return self._ensure_partner_from_cliente(self.cliente_id)
        for l in self.line_ids:
            if l.cliente_id:
                return self._ensure_partner_from_cliente(l.cliente_id)
        return False

    
    # Abre una acción de ventana list/form con los adjuntos del registro actual.
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
    # Placeholder de “Intereses” (no implementado). Lanza excepción “pendiente”.
    def action_placeholder_interest(self):
        self.ensure_one()
        raise ValidationError(_('Intereses: pendiente de implementar.'))
    
    # Devuelve la acción estándar para cerrar el formulario actual y regresar a la lista principal.
    def action_close_form(self):
        """Regresa a la lista principal de facturas UI (tree/form)."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas'),
            'res_model': self._name,
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [],  # sin filtro
        }
    
    # === BLOQUEO: no agregar nuevas líneas en Egresos ===
    # === BLOQUEO en Egresos: permitir reemplazos (unlink+create) pero NO nuevas altas netas ===
    def write(self, vals):
        if 'line_ids' in vals:
            cmds = vals['line_ids'] or []
            for rec in self:
                if rec.tipo != 'E':
                    continue

                start = len(rec.line_ids)
                end_count = start
                saw_add = False
                saw_del = False

                for c in cmds:
                    if not (isinstance(c, (list, tuple)) and c):
                        continue
                    op = c[0]
                    if op == 0:              # (0,0,vals) -> create
                        end_count += 1
                        saw_add = True
                    elif op == 1:            # (1,id,vals) -> update
                        pass
                    elif op == 2:            # (2,id) -> unlink
                        end_count -= 1
                        saw_del = True
                    elif op == 5:            # (5,0,0) -> clear
                        end_count = 0
                        saw_del = True
                    elif op == 6:            # (6,0,[ids]) -> replace set
                        ids = c[2] if len(c) > 2 else []
                        end_count = len(ids)
                        # esto puede actuar como clear+add, lo tratamos como reemplazo controlado
                        saw_add = bool(ids)
                        saw_del = True

                # Si el conteo final es MAYOR que el inicial (altas netas) y no es prefill → bloquear
                if end_count > start and not self.env.context.get('egreso_prefill'):
                    raise ValidationError(_("En Egresos no puedes agregar nuevas líneas. Ajusta cantidades o elimina las existentes."))

            # Si detectamos patrón de reemplazo (hay create y también delete), pasamos una bandera
            # para que el create de líneas lo permita como "swap" y no como alta nueva.
            if any(isinstance(c, (list, tuple)) and c and c[0] == 0 for c in cmds) and \
               any(isinstance(c, (list, tuple)) and c and c[0] in (2, 5, 6) for c in cmds):
                return super(FacturaUI, self.with_context(egreso_line_swap=True)).write(vals)

        return super().write(vals)


    
    # Helper: genera comandos (0,0,vals) clonando conceptos de una factura origen (sin enlaces)
    # para precargar egresos/NC y permitir ajustes posteriores.
    def _prepare_lines_from_origin(self, origin):
        """Devuelve comandos (0,0,vals) clonando conceptos de la factura origen."""
        self.ensure_one()
        new_lines = []
        for ol in origin.line_ids:
            new_lines.append((0, 0, {
                'empresa_id':   self.empresa_id.id,
                'cliente_id':   origin.cliente_id.id if origin.cliente_id else False,
                'line_type':    ol.line_type or 'sale',
                'producto_id':  ol.producto_id.id,
                'descripcion':  ol.descripcion,
                'cantidad':     ol.cantidad,   # editable para devoluciones parciales
                'precio':       ol.precio,
                'iva_ratio':    ol.iva_ratio,
                'ieps_ratio':   ol.ieps_ratio,
                # IMPORTANTE: NO poner sale_id / transaccion_id / source_model
            }))
        return new_lines

    # Desde un Ingreso timbrado, crea una Nota de crédito (Egreso) precargada (encabezado/líneas)
    # y abre el formulario de la nueva NC para revisión/timbrado.
    def action_prepare_credit_note(self):
        """Desde Ingreso timbrado, crear NC (Egreso) prellenando conceptos del origen."""
        self.ensure_one()
        if self.tipo != 'I' or self.state != 'stamped':
            raise ValidationError(_('Solo puedes crear una Nota de crédito desde un Ingreso timbrado.'))

        nc_vals = {
            'empresa_id': self.empresa_id.id,
            'sucursal_id': self.sucursal_id.id,
            'cliente_id': self.cliente_id.id,
            'tipo': 'E',
            'egreso_tipo': 'nc',        # ← explícito
            'metodo': 'PUE',            # PUE en egresos
            'forma': self.forma,
            'moneda': self.moneda or 'MXN',
            'uso_cfdi': self.uso_cfdi or 'G02',
            'origin_factura_id': self.id,
        }

        # Prefill de conceptos exactamente como cuando eliges la factura origen
        nc_lines = self._prepare_lines_from_origin(self)

        # Crea la NC con encabezado + líneas
        nc = self.with_context(egreso_prefill=True).create({**nc_vals, 'line_ids': nc_lines})


        # Abrir la NC en formulario para revisar/ajustar (cantidades, etc.) y timbrar
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nota de crédito'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': nc.id,
            'target': 'current',
        }
    
    def action_prepare_payment(self):
        """Desde Ingreso timbrado, crear Pago (tipo P) prellenando encabezado y monto=saldo."""
        self.ensure_one()
        if self.tipo != 'I' or self.state != 'stamped':
            raise ValidationError(_('Solo puedes crear un Pago desde un Ingreso timbrado.'))
        if max(self.saldo or 0.0, 0.0) <= 0.0:
            raise ValidationError(_('La factura ya no tiene saldo por pagar.'))

        p_vals = {
            'empresa_id': self.empresa_id.id,
            'sucursal_id': self.sucursal_id.id,
            'cliente_id': self.cliente_id.id,
            'tipo': 'P',
            'moneda': self.moneda or 'MXN',
            'origin_factura_id': self.id,
            'pago_importe': max(self.saldo or 0.0, 0.0),
            'forma': '03',
        }
        pago = self.create(p_vals)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Complemento de Pago'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': pago.id,
            'target': 'current',
        }


    
    # ===== Botones para descargar/recuperar XML =====
    # Localiza el adjunto XML del CFDI priorizando: account.move → pagos relacionados → la propia
    # FacturaUI → documentos del engine (mx.cfdi.document). Devuelve el attachment o vacío.
    def _find_cfdi_xml_attachment(self):
        """Regresa attachment XML si existe (prioriza account.move → pagos → facturas.factura → mx.cfdi.document)."""
        self.ensure_one()
        Att = self.env['ir.attachment']

        # 1) Anexos del MOVE (preferido)
        if self.move_id:
            att = Att.search([
                ('res_model', '=', 'account.move'),
                ('res_id', '=', self.move_id.id),
                ('mimetype', 'in', ['application/xml', 'text/xml']),
            ], limit=1, order='id desc')
            if att:
                return att

        # 2) Complementos de pago (pagos reconciliados con la factura)
        if self.move_id:
            Pay = self.env['account.payment']
            payments = Pay.search([('reconciled_invoice_ids', 'in', self.move_id.id),
                                   ('state', '=', 'posted')], limit=10)
            if payments:
                att = Att.search([
                    ('res_model', '=', 'account.move'),
                    ('res_id', 'in', payments.mapped('move_id').ids),
                    ('mimetype', 'in', ['application/xml', 'text/xml']),
                ], limit=1, order='id desc')
                if att:
                    return att

        # 3) Fallback: adjunto en la propia FacturaUI
        att = Att.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('mimetype', 'in', ['application/xml', 'text/xml']),
        ], limit=1, order='id desc')
        if att:
            return att

        # 4) Fallback: documento del engine (si existe tu modelo mx.cfdi.document)
        Doc = self.env['mx.cfdi.document'] if 'mx.cfdi.document' in self.env else False
        if Doc and self.uuid:
            doc_ids = Doc.search([
                ('origin_model', '=', 'account.move' if self.move_id else self._name),
                ('origin_id', '=', self.move_id.id if self.move_id else self.id),
                ('uuid', '=', self.uuid),
            ]).ids
            if doc_ids:
                att = Att.search([
                    ('res_model', '=', 'mx.cfdi.document'),
                    ('res_id', 'in', doc_ids),
                    ('mimetype', 'in', ['application/xml', 'text/xml']),
                ], limit=1, order='id desc')
                if att:
                    return att

        return self.env['ir.attachment']  # vacío

    # Fuerza la descarga del XML CFDI hallado por _find_cfdi_xml_attachment(). Valida que exista uuid.
    def action_download_xml(self):
        """Forzar descarga del XML CFDI (igual que ventas.action_download_cfdi)."""
        self.ensure_one()
        if not self.uuid:
            raise ValidationError(_("Aún no hay UUID. Timbra o recupera el XML primero."))

        att = self._find_cfdi_xml_attachment()
        if not att:
            raise ValidationError(_("No hay XML adjunto para esta factura."))

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{att.id}?download=true',
            'target': 'self',
        }

    # Consulta al proveedor SW por UUID (DataWarehouse), adjunta el XML (y acuse si llega) a
    # account.move y a la FacturaUI, y dispara la descarga. Requiere contexto empresa_id (se usa self.empresa_id).
    def action_fetch_xml_from_sw(self):
        """Descarga el XML desde SW (PAC) y lo adjunta al move y a la FacturaUI; luego fuerza descarga."""
        self.ensure_one()
        if not self.uuid:
            raise ValidationError(_('No hay UUID para recuperar.'))

        # Usa exactamente el mismo proveedor que en ventas
        engine = self.env['mx.cfdi.engine'].with_context(empresa_id=self.empresa_id.id)
        provider = engine._get_provider()

        data = provider.download_xml_by_uuid(self.uuid, tries=10, delay=1.0)
        if not data or not data.get('xml'):
            raise UserError(_('SW no devolvió XML para el UUID %s.') % self.uuid)

        Att = self.env['ir.attachment']

        # A) Adjuntar al MOVE si existe
        if self.move_id:
            Att.sudo().create({
                'name': f"{self.uuid}.xml",
                'res_model': 'account.move',
                'res_id': self.move_id.id,
                'type': 'binary',
                'datas': base64.b64encode(data['xml']).decode('ascii'),
                'mimetype': 'application/xml',
                'description': _('CFDI timbrado %s (descargado de SW)') % self.uuid,
            })

        # B) Copia en FacturaUI
        Att.sudo().create({
            'name': f"{self.uuid}-factura_ui.xml",
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'datas': base64.b64encode(data['xml']).decode('ascii'),
            'mimetype': 'application/xml',
            'description': _('CFDI timbrado %s (copia UI)') % self.uuid,
        })

        # C) Acuse, si viene
        if data.get('acuse'):
            Att.sudo().create({
                'name': f"acuse-{self.uuid}.xml",
                'res_model': self._name,
                'res_id': self.id,
                'type': 'binary',
                'datas': base64.b64encode(data['acuse']).decode('ascii'),
                'mimetype': 'application/xml',
                'description': _('Acuse CFDI %s (SW DW)') % self.uuid,
            })

        # D) Forzar descarga inmediata del XML recién guardado (prioriza MOVE si existe)
        att = self._find_cfdi_xml_attachment()
        if att:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{att.id}?download=true',
                'target': 'self',
            }
        return self.action_open_attachments()
    
    # ==== fin botones XML ====

        # ======================== Cancel Helpers ========================
    def _ensure_cancel_window_30d(self):
        self.ensure_one()
        dt = self.fecha or fields.Datetime.now()
        delta = fields.Datetime.now() - dt
        if delta.days > 30:
            raise ValidationError(_('No puedes cancelar: la fecha de emisión excede 30 días (emitida el %s).') % (fields.Datetime.to_string(dt),))

    def _check_no_children_before_cancel(self):
        """Para Ingresos: asegurar que NO hay E/P vigentes (no-cancelados) ligados."""
        self.ensure_one()
        if self.tipo != 'I':
            return
        hijos = self.env['facturas.factura'].search([
            ('origin_factura_id', '=', self.id),
            ('tipo', 'in', ['E', 'P']),
            ('state', '!=', 'canceled'),
        ], limit=1)
        if hijos:
            raise ValidationError(_('Cancela primero los Egresos/Pagos relacionados antes de cancelar la factura principal.'))

    def _pac_cancel(self, motivo='02', folio_sustitucion=None):
        self.ensure_one()
        if self.state != 'stamped' or not (self.uuid or '').strip():
            return
        engine = self.env['mx.cfdi.engine'].with_context(empresa_id=self.empresa_id.id)
        res = engine.cancel_cfdi(
            origin_model='account.move' if self.move_id else self._name,
            origin_id=self.move_id.id if self.move_id else self.id,
            uuid=self.uuid,
            motivo=motivo or '02',
            folio_sustitucion=folio_sustitucion
        )
        status = (res.get('status') if isinstance(res, dict) else res)
        self.message_post(body=_('CFDI cancelado en PAC. Respuesta: %s') % status)

        # 👇 ADJUNTAR ACUSE
        try:
            acuse = isinstance(res, dict) and res.get('acuse')
            if acuse:
                self.env['ir.attachment'].sudo().create({
                    'name': f"acuse-cancel-{self.uuid}.xml",
                    'res_model': self._name,
                    'res_id': self.id,
                    'type': 'binary',
                    'datas': base64.b64encode(acuse).decode('ascii'),
                    'mimetype': 'application/xml',
                    'description': _('Acuse de cancelación CFDI %s') % self.uuid,
                })
        except Exception:
            pass


    def _cancel_account_move(self):
        """Intenta cancelar el account.move contable si existe."""
        self.ensure_one()
        mv = self.move_id
        if not mv:
            return
        try:
            if mv.state == 'posted':
                # Odoo 18: cancelar asiento (si diario permite cancelación)
                mv.button_cancel()
            elif mv.state not in ('cancel',):
                mv.button_cancel()
        except Exception:
            # Fallback: draft -> cancel
            try:
                mv.button_draft()
                mv.button_cancel()
            except Exception as e:
                self._logger.warning("No se pudo cancelar el move %s: %s", mv.id, e)


    def _disable_own_transactions(self):
        """Deshabilita y neutraliza (sin borrar) las transacciones creadas por ESTA factura,
           quitando su efecto en estado de cuenta y rompiendo el vínculo con el cliente/venta.
        """
        used_legacy = False
        count_token = 0
        count_legacy = 0
    
        self.ensure_one()
        try:
            Tx = self.env['transacciones.transaccion'].sudo()
        except KeyError:
            return
    
        # 1) Búsqueda precisa por token
        token = self._own_ref_token()
        dom = [('referencia', 'ilike', token)]
        if 'sucursal_id' in Tx._fields and self.sucursal_id:
            dom.append(('sucursal_id', '=', self.sucursal_id.id))
        if 'empresa_id_helper' in Tx._fields:
            dom.append(('empresa_id_helper', '=', self.empresa_id.id))
        if 'tipo' in Tx._fields:
            if self.tipo == 'P':
                dom.append(('tipo', '=', '11'))
            elif self.tipo == 'E':
                dom.append(('tipo', '=', '6' if (self.egreso_tipo or '') == 'dev' else '10'))
    
        txs = Tx.search(dom, limit=200)
        count_token = len(txs)
    
        if not txs:
            txs = Tx.search([('referencia', 'ilike', token)], limit=200)
            count_token = len(txs)
    
        # 2) Fallback LEGACY (si no traían token)
        if not txs:
            refs = []
            if self.move_id and getattr(self.move_id, 'name', False):
                refs.append(self.move_id.name)
                refs.append('Pago a factura %s' % self.move_id.name)
            if (self.uuid or '').strip():
                refs.append(self.uuid)
    
            legacy_dom = [('id', '=', 0)]
            for r in refs:
                legacy_dom = OR([legacy_dom, [('referencia', 'ilike', r)]])
            tight = []
            if 'sucursal_id' in Tx._fields and self.sucursal_id:
                tight.append(('sucursal_id', '=', self.sucursal_id.id))
            if 'empresa_id_helper' in Tx._fields:
                tight.append(('empresa_id_helper', '=', self.empresa_id.id))
            if 'tipo' in Tx._fields:
                if self.tipo == 'P':
                    tight.append(('tipo', '=', '11'))
                elif self.tipo == 'E':
                    tight.append(('tipo', '=', '6' if (self.egreso_tipo or '') == 'dev' else '10'))
    
            legacy_dom = tight + legacy_dom
            txs = Tx.search(legacy_dom, limit=200)
            count_legacy = len(txs)
            used_legacy = True
    
        if not txs:
            self._logger.info(
                "CANCEL TX | fact_id=%s token=%s matched_by_token=%s matched_by_legacy=%s",
                self.id, token, count_token, count_legacy
            )
            return
    
        self._logger.info(
            "CANCEL TX | fact_id=%s token=%s matched_by_token=%s matched_by_legacy=%s",
            self.id, token, count_token, count_legacy
        )
    
        # 3) Neutralizar impacto en estado de cuenta (sin borrar)
        neutral_vals = {}
        # a) Desactivar o marcar como canceladas
        if 'active' in Tx._fields:
            neutral_vals['active'] = False
        if 'state' in Tx._fields and any(a == 'cancelled' for a, _ in (Tx._fields['state'].selection(Tx.env) or [])):
            neutral_vals['state'] = 'cancelled'
    
        # b) Romper relación con el cliente (directa o indirecta)
        if 'venta_id' in Tx._fields:
            neutral_vals['venta_id'] = False       # evita relación via venta → cliente
        if 'cliente_id' in Tx._fields:
            neutral_vals['cliente_id'] = False     # por si tu modelo sí lo tiene
        if 'cliente_rfc_helper' in Tx._fields:
            neutral_vals['cliente_rfc_helper'] = False  # por si tu estado usa este helper
    
        # c) Si tu modelo tiene un flag para reportes, márcalo
        if 'ignorar_estado_cuenta' in Tx._fields:
            neutral_vals['ignorar_estado_cuenta'] = True
    
        if neutral_vals:
            try:
                txs.write(neutral_vals)
            except Exception as e:
                self._logger.warning("CANCEL TX | no se pudieron neutralizar campos: %s", e)
                # fallback ultra-conservador: deja al menos una marca visible
                for t in txs:
                    try:
                        t.write({'referencia': (t.referencia or '') + ' [CANCELADA/NEUTRALIZADA]'})
                    except Exception:
                        pass
                    
        # 4) Cambio “no destructivo” por si no hay active/state: marca en referencia
        if 'active' not in Tx._fields and 'state' not in Tx._fields:
            for t in txs:
                try:
                    t.write({'referencia': (t.referencia or '') + ' [CANCELADA]'})
                except Exception:
                    pass
                
        # 5) Flush para asegurar persistencia antes de seguir
        try:
            Tx.flush()
        except Exception:
            pass
        
        self._logger.info("CANCEL TX | disabled/neutralized=%s", len(txs))




    def _release_sales_after_cancel(self):
        """Pone ventas ligadas en estado facturable y limpia vínculos mínimos."""
        ventas_from_lines = self.env['ventas.venta'].browse(
            list({l.sale_id.id for l in self.line_ids if l.sale_id})
        )
        ventas = (self.venta_ids | ventas_from_lines).sudo()
        if not ventas:
            return
        # Elegir el mejor estado "facturable"
        tgt = 'confirmed'
        if 'state' in ventas._fields:
            sel = [a for a, _ in (ventas._fields['state'].selection(ventas.env) or [])]
            if 'to_invoice' in sel:
                tgt = 'to_invoice'
            elif 'confirmed' in sel:
                tgt = 'confirmed'
            elif 'draft' in sel:
                tgt = 'draft'
        vals = {'state': tgt}
        if 'move_id' in ventas._fields:
            vals['move_id'] = False
        try:
            ventas.write(vals)
        except Exception as e:
            self._logger.warning("No se pudo actualizar ventas tras cancelación: %s", e)
    # ======================== /Cancel Helpers ========================


    
    # Onchange: si la factura origen no coincide en empresa/cliente con el encabezado, la limpia.
    @api.onchange('cliente_id', 'empresa_id', 'origin_factura_id')
    def _onchange_origin_guard(self):
        for r in self:
            if not r.origin_factura_id:
                continue
            # 1) Si por alguna razón la origen no está timbrada, límpiala
            if r.origin_factura_id.state != 'stamped':
                r.origin_factura_id = False
                continue
            # 2) Empresa/cliente deben coincidir
            if (r.empresa_id and r.origin_factura_id.empresa_id != r.empresa_id) or \
               (r.cliente_id and r.origin_factura_id.cliente_id != r.cliente_id):
                r.origin_factura_id = False


    def _is_service_line(self, line):
        """Intenta detectar servicios para no tocar stock."""
        # Si tu productos.producto expone bandera propia, úsala:
        if getattr(line.producto_id, 'is_service', False):
            return True
        # O resuelve product.product para revisar detailed_type
        pp = False
        ensure = getattr(line.producto_id, 'ensure_product_product', None)
        if callable(ensure):
            try:
                pp = ensure()
            except Exception:
                pass
        return getattr(pp, 'detailed_type', '') == 'service'

    def _apply_stock_on_ingreso(self):
        """Descuenta stock por línea (solo productos, no servicios)."""
        self.ensure_one()
        Stock = self.env['stock.sucursal.producto'].sudo()
        tot = 0.0

        for l in self.line_ids:
            if not l.producto_id or self._is_service_line(l):
                continue
            qty = l.cantidad or 0.0
            if qty > 0:
                Stock.remove_stock(self.sucursal_id, l.producto_id, qty)
                tot += qty
        self._logger.info(
            "STOCK | OUT | fact_id=%s sucursal=%s total_qty=%.4f",
            self.id, (self.sucursal_id.id if self.sucursal_id else None), tot
        )
    
    def action_cancel(self):
        self.ensure_one()
        # 1) Ventana de 30 días
        self._ensure_cancel_window_30d()
        # 2) Si es Ingreso: no permitir si tiene E/P vigentes
        self._check_no_children_before_cancel()
        # 3) Cancelación en PAC (si aplica)
        try:
            self._pac_cancel(motivo=self.env.context.get('cfdi_cancel_reason', '02'))
        except Exception as e:
            # si quieres abortar cuando PAC falle, descomenta la siguiente línea
            # raise
            self._logger.warning("PAC cancel falló (se continuará con cancelación interna): %s", e)
        # 4) Revertir stock según tipo
        Stock = self.env['stock.sucursal.producto'].sudo()
        if self.state == 'stamped':
            if self.tipo == 'I':
                # Regresar lo que se descontó al timbrar
                for l in self.line_ids:
                    if not l.producto_id or self._is_service_line(l):
                        continue
                    qty = l.cantidad or 0.0
                    if qty > 0:
                        Stock.add_stock(self.sucursal_id, l.producto_id, qty)
            elif self.tipo == 'E':
                # Si fue devolución, retirar lo que se había regresado
                if (self.egreso_tipo or '') == 'dev':
                    for l in self.line_ids:
                        if not l.producto_id or self._is_service_line(l):
                            continue
                        qty = l.cantidad or 0.0
                        if qty > 0:
                            Stock.remove_stock(self.sucursal_id, l.producto_id, qty)
                # Además: deshabilitar transacciones creadas por este egreso
                try:
                    self._disable_own_transactions()
                except Exception as e:
                    self._logger.warning("No se pudieron deshabilitar transacciones del egreso: %s", e)
            elif self.tipo == 'P':
                # Pago: deshabilitar transacción de pago (tipo 11) creada por este registro
                try:
                    self._disable_own_transactions()
                except Exception as e:
                    self._logger.warning("No se pudieron deshabilitar transacciones del pago: %s", e)

        # --- NUEVO: reponer contadores en la factura origen ---
        origin = self.origin_factura_id
        if origin:
            try:
                if self.tipo == 'P':
                    self._restore_amount_counters_on_origin(self.pago_importe)
                elif self.tipo == 'E':
                    if (self.egreso_tipo or '') == 'dev':
                        self._restore_dev_counters_on_origin()
                    else:  # 'nc'
                        self._restore_amount_counters_on_origin(self.importe_total)
            except Exception as e:
                self._logger.warning("No se pudieron restaurar contadores en origen: %s", e)
    
            # Forzar recompute de saldo en la origen (como haces al timbrar)
            try:
                origin.write({'state': origin.state})
            except Exception:
                pass
            # (opcional) refresca ventas ligadas
            ventas_orig = origin.venta_ids | self.env['ventas.venta'].browse(
                list({l.sale_id.id for l in origin.line_ids if l.sale_id})
            )
            if ventas_orig:
                try:
                    ventas_orig.write({'state': ventas_orig[0].state})
                except Exception:
                    pass

        # 5) Cancelar el asiento contable si existe (I/E)
        try:
            self._cancel_account_move()
        except Exception as e:
            self._logger.warning("Falló cancelación del move: %s", e)
        # 6) Marcar estado cancelado en UI
        self.write({'state': 'canceled'})
        self._logger.info(
            "CFDI FLOW | CANCELED | id=%s tipo=%s uuid=%s move_id=%s",
            self.id, self.tipo, (self.uuid or ''), (self.move_id.id if self.move_id else None)
        )

        # 7) Si es Ingreso: liberar ventas para re-facturar
        if self.tipo == 'I':
            try:
                self._release_sales_after_cancel()
            except Exception as e:
                self._logger.warning("No se pudieron liberar ventas: %s", e)
        # 8) Evitar posteriores E/P sobre esta factura (ya lo cubre el domain/state, esto es solo seguridad)
        # (nada adicional requerido aquí)
        return self.action_close_form()


    
    # ============================== Fin utils ==============================

    # =========================== Helpers ===========================
    # Establece la moneda de la UI a partir del parámetro 'facturacion_ui.currency_id' o MXN por defecto.
    @api.depends('empresa_id')
    def _compute_currency(self):
        ICP = self.env['ir.config_parameter'].sudo()
        val = (ICP.get_param('facturacion_ui.currency_id') or '').strip()

        cur = False
        if val:
            # 1) Si es ID numérico
            if val.isdigit():
                cur = self.env['res.currency'].browse(int(val))
            # 2) Si parece xmlid: ej. 'base.MXN'
            elif '.' in val:
                cur = self.env.ref(val, raise_if_not_found=False)
            else:
                # 3) Código/Nombre de moneda: 'MXN', 'USD', etc.
                Cur = self.env['res.currency']
                cur = Cur.search([('name', '=', val)], limit=1) or Cur.search([('name', 'ilike', val)], limit=1)

        # 4) Fallback a MXN por xmlid
        if not cur:
            cur = self.env.ref('base.MXN', raise_if_not_found=False)

        # 5) Si la moneda está inactiva o no existe, caer a la moneda activa de la compañía
        if not cur or (hasattr(cur, 'active') and not cur.active):
            company_cur = self.env.company.currency_id
            cur = company_cur if (company_cur and company_cur.active) else False

        for r in self:
            r.currency_id = cur or False




    importe_total = fields.Monetary(string='Importe', currency_field='currency_id',
                                    compute='_compute_totales', store=True)
    saldo = fields.Monetary(string='Saldo', currency_field='currency_id',
                            compute='_compute_totales', store=True)

    # Egreso: relación obligatoria a la factura de Ingreso
    origin_factura_id = fields.Many2one(
        'facturas.factura',
        string='Factura origen',
        domain="[('tipo','=','I'), ('state','=','stamped'), \
                ('empresa_id','=', empresa_id), \
                ('sucursal_id','=', sucursal_id), \
                ('cliente_id','=', cliente_id)]",
        copy=False,
        index=True,
    )

    origin_move_id = fields.Many2one(
        'account.move', string='Factura contable origen',
        related='origin_factura_id.move_id', store=True, readonly=True
    )

    # Calcula importes por encabezado (suma de líneas) y, para I/E con PPD, el saldo = importe total.
    @api.depends('line_ids.total', 'metodo', 'tipo', 'state', 'pago_importe')
    def _compute_totales(self):
        for r in self:
            total_lineas = sum((l.total or 0.0) for l in r.line_ids)
            r.importe_total = (r.pago_importe or 0.0) if r.tipo == 'P' else total_lineas

            base = 0.0
            if r.tipo == 'I':
                # En PPD el saldo parte del total; en PUE parte de 0
                base = r.importe_total if (r.metodo or '').upper() == 'PPD' else 0.0
                # Restar créditos aplicados (E y P) SIEMPRE, también en PUE (puede quedar negativo)
                try:
                    base -= (r._applied_credits_total() or 0.0)
                except Exception:
                    # no rompas el compute si algo falla, deja el base
                    pass
                
            # En tipo 'E' forzamos PUE en otros puntos; aquí normaliza
            if r.tipo == 'E':
                base = 0.0  # el saldo relevante es el de la factura original
    
            r.saldo = max(base, 0.0)


    def _applied_credits_total(self):
        """Total de Egresos (NC/DEV) y Pagos timbrados/aplicados que impactan a esta factura."""
        self.ensure_one()
        E = self.env['facturas.factura']
        aplicados = E.search([
            ('tipo', 'in', ['E', 'P']),
            ('state', '=', 'stamped'),
            ('origin_factura_id', '=', self.id),
        ])
        total = 0.0
        for e in aplicados:
            if e.tipo == 'P':
                total += (e.pago_importe or 0.0)
            else:
                total += (e.importe_total or 0.0)
        return total



    # Calcula cuántos adjuntos (ir.attachment) tiene el registro para mostrar un contador.
    def _compute_attachment_count(self):
        Att = self.env['ir.attachment']
        for r in self:
            r.attachment_count = Att.search_count([('res_model', '=', r._name), ('res_id', '=', r.id)])

    # Valida reglas de negocio antes de timbrar:
        # - Debe haber al menos una línea y todas de la misma sucursal/empresa/cliente.
        # - En Egreso: requiere factura origen y mismo cliente que el origen.
        # - Evita facturar transacciones canceladas.
        # - En Egreso, si el método no es PUE lo corrige a PUE.
    def _check_consistency(self):
        self.ensure_one()
        bad = self.line_ids.filtered(lambda l: l.sale_id and l.sale_id.sucursal_id != self.sucursal_id)
        try:
            super()._check_consistency()
        except AttributeError:
            pass

        self.ensure_one()

        if self.tipo in ('I', 'E') and not (self.uso_cfdi or '').strip():
            raise ValidationError(_('Selecciona el "Uso CFDI" para facturas de Ingreso/Egreso.'))
        
        if self.tipo in ('I', 'E'):
            if not (self.metodo or '').strip():
                raise ValidationError(_('Selecciona el "Método de pago" (PUE/PPD).'))
            if (self.metodo or '').upper() == 'PPD' and (self.forma or '').strip() != '99':
                raise ValidationError(_('Con PPD la Forma debe ser "99 - Por definir".'))


        if self.tipo in ('I', 'E') and not self.line_ids:
            raise ValidationError(_('Agrega al menos un concepto a la factura.'))
        if bad:
            raise ValidationError(_('Todas las transacciones deben pertenecer a la sucursal seleccionada.'))

        emp_ids = {l.empresa_id.id for l in self.line_ids if l.empresa_id}
        if len(emp_ids) > 1 or (self.empresa_id and emp_ids and self.empresa_id.id not in emp_ids):
            raise ValidationError(_('Todas las líneas deben pertenecer a la misma empresa.'))
        if self.empresa_id and not emp_ids:
            self.line_ids.write({'empresa_id': self.empresa_id.id})

        # Asegurar PUE en egresos (sin romper flujo)
        if self.tipo == 'E' and (self.metodo or '').upper() != 'PUE':
            self.metodo = 'PUE'

        # Egresos: validar cliente y factura origen
        if self.tipo == 'E':
            if self.origin_factura_id and self.origin_factura_id.state != 'stamped':
                raise ValidationError(_('La factura origen debe estar TIMBRADA para poder hacer un Egreso.'))

            if not self.origin_factura_id:
                raise ValidationError(_('En un Egreso debes seleccionar la "Factura origen".'))
            if (self.origin_factura_id.cliente_id and self.cliente_id 
                and self.origin_factura_id.cliente_id.id != self.cliente_id.id):
                raise ValidationError(_('El cliente del Egreso debe coincidir con el de la factura origen.'))
            


        # ===== Validaciones extra para E y P =====
        if self.tipo == 'E':
            # 1) Debe tener factura origen (ya lo tienes arriba)
            # 2) Validar por tipo de egreso
            if self.egreso_tipo == 'dev':
                # No exceder cantidades disponibles por producto en la factura origen
                # Suma solicitada por producto en este egreso
                req_by_prod = {}
                for l in self.line_ids:
                    if l.producto_id:
                        req_by_prod[l.producto_id.id] = req_by_prod.get(l.producto_id.id, 0.0) + (l.cantidad or 0.0)

                # Suma disponible por producto (en líneas del origen)
                avail_by_prod = {}
                for ol in self.origin_factura_id.line_ids:
                    if ol.producto_id:
                        avail_by_prod[ol.producto_id.id] = avail_by_prod.get(ol.producto_id.id, 0.0) + (ol.qty_dev_available or 0.0)

                for pid, qty_req in req_by_prod.items():
                    qty_av = avail_by_prod.get(pid, 0.0)
                    if qty_req > qty_av + 1e-6:
                        raise ValidationError(_("Devolución excede cantidad disponible para el producto ID %s: solicitada=%.2f, disponible=%.2f") % (pid, qty_req, qty_av))

            elif self.egreso_tipo == 'nc':
                # No exceder total disponible de crédito (suma de total_dev_available en el origen)
                req_total = sum((l.total or 0.0) for l in self.line_ids)
                avail_total = sum((ol.total_dev_available or 0.0) for ol in self.origin_factura_id.line_ids)
                if req_total > avail_total + 1e-6:
                    raise ValidationError(_("Nota de crédito excede el monto acreditable: solicitado=%.2f, disponible=%.2f") % (req_total, avail_total))

        elif self.tipo == 'P':
            if self.origin_factura_id and self.origin_factura_id.state != 'stamped':
                raise ValidationError(_('La factura origen debe estar TIMBRADA para poder hacer un Pago.'))

            if not self.origin_factura_id:
                raise ValidationError(_('En un Pago debes seleccionar la "Factura origen".'))
            if (self.pago_importe or 0.0) <= 0.0:
                raise ValidationError(_('Captura un importe de pago mayor que 0.'))
            # No pagar arriba del saldo
            saldo_disp = max(self.origin_factura_id.saldo or 0.0, 0.0)
            if (self.pago_importe or 0.0) - 1e-6 > saldo_disp:
                raise ValidationError(_("El pago (%.2f) excede el saldo disponible (%.2f) de la factura origen.") % (self.pago_importe, saldo_disp))
            # La forma de pago del nodo Pago es obligatoria
            if not (self.forma or '').strip():
                raise ValidationError(_('Selecciona la Forma de pago del complemento (ej. 03 Transferencia).'))
            # En pago no debe haber conceptos
            if self.line_ids:
                raise ValidationError(_('En un Pago no debes capturar conceptos; solo importe y factura origen.'))



        clientes = {l.cliente_id.id for l in self.line_ids if l.cliente_id}
        if len(clientes) > 1:
            raise ValidationError(_('Todas las líneas deben ser del mismo cliente.'))

        if any(l.source_model == 'transacciones.transaccion' and l.sale_state == 'cancelled' for l in self.line_ids):
            raise ValidationError(_('Hay transacciones de ventas canceladas.'))

    def unlink(self):
        for r in self:
            if r.state not in ('draft', 'canceled'):
                raise ValidationError(_('No puedes eliminar una factura que no esté en Borrador o Cancelada.'))
        return super().unlink()
    
    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        cid = (self.env.context.get('cliente_id') 
               or self.env.context.get('default_cliente_id'))
        if cid:
            cli = self.env['clientes.cliente'].browse(cid)
            rfc = (getattr(cli, 'rfc', False) or getattr(cli, 'vat', False) 
                   or (getattr(getattr(cli, 'persona_id', False), 'rfc', False) or False))
            vals['cliente_rfc'] = rfc or False
        return vals
    
    def _restore_dev_counters_on_origin(self):
        origin = self.origin_factura_id
        if not origin:
            return
        # DEV: regresamos cantidades hasta el tope de 'cantidad'
        pend_by_prod = {}
        for l in self.line_ids:
            if l.producto_id:
                pend_by_prod[l.producto_id.id] = pend_by_prod.get(l.producto_id.id, 0.0) + (l.cantidad or 0.0)

        for ol in origin.line_ids.sorted('id'):
            pid = ol.producto_id.id if ol.producto_id else False
            if not pid:
                continue
            pend = pend_by_prod.get(pid, 0.0)
            if pend <= 0:
                continue
            cap = max((ol.cantidad or 0.0) - (ol.qty_dev_available or 0.0), 0.0)
            add = min(cap, pend)
            if add > 0:
                new_qty = (ol.qty_dev_available or 0.0) + add
                # devuelve proporcionalmente el importe acreditable
                ratio = add / (ol.cantidad or 1.0)
                new_total_av = min((ol.total_dev_available or 0.0) + (ol.total or 0.0) * ratio, (ol.total or 0.0))
                ol.write({'qty_dev_available': new_qty, 'total_dev_available': new_total_av})
                pend_by_prod[pid] = pend - add

    def _restore_amount_counters_on_origin(self, amount):
        """Para NC y Pago: reponer 'total_dev_available' en el origen hasta su tope (total)."""
        origin = self.origin_factura_id
        if not origin:
            return
        pend = float(amount or 0.0)
        for ol in origin.line_ids.sorted('id'):
            if pend <= 1e-9:
                break
            cap = max((ol.total or 0.0) - (ol.total_dev_available or 0.0), 0.0)
            add = min(cap, pend)
            if add > 1e-9:
                ol.write({'total_dev_available': (ol.total_dev_available or 0.0) + add})
                pend -= add

    def _own_ref_token(self):
        """Token único para rastrear transacciones creadas por ESTA FacturaUI y evitar falsos positivos."""
        self.ensure_one()
        return f"[FUI#{self.id}]"




    # =========================== Fin Helpers ===========================




# models/factura.py
class FacturaUILine(models.Model):
    _name = 'facturas.factura.line'
    _description = 'Concepto a facturar (UI)'
    _logger = _logger
    _sql_constraints = [
        ('uniq_tx_per_fact', 'unique(factura_id, transaccion_id)',
         'La misma transacción no puede agregarse dos veces a la misma factura.')
    ]

    factura_id  = fields.Many2one('facturas.factura', required=True, ondelete='cascade')
    empresa_id  = fields.Many2one('empresas.empresa', required=True, index=True)
    cliente_id = fields.Many2one('clientes.cliente', required=True, index=True, ondelete='restrict')


    # Tipos de origen
    line_type   = fields.Selection([('sale','Venta'), ('charge','Cargo'), ('interest','Interés')], required=True, default='sale',)
    source_model= fields.Char()   # 'transacciones.transaccion' | 'cargosdetail.cargodetail' | ...
    source_id   = fields.Integer()
    sale_id     = fields.Many2one('ventas.venta', string='Venta')
    sale_state  = fields.Selection(related='sale_id.state', store = True)

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

    # === Contadores de disponibilidad para DEV/NC (se inicializan al timbrar el Ingreso)
    qty_dev_available   = fields.Float(string='Disp. devolución (cant)', default=0.0)
    total_dev_available = fields.Float(string='Disp. crédito ($)', default=0.0)



    # Seguimiento de facturación por transacción
    transaccion_id = fields.Many2one('transacciones.transaccion', string='Transacción (si aplica)')
    qty_to_invoice = fields.Float(default=0.0)  # para parciales
    qty_invoiced   = fields.Float(default=0.0)

    # Transforma líneas UI a comandos (0,0,vals) para account.move.invoice_line_ids en ‘company’:
    # resuelve taxes por porcentaje, busca product.product de forma robusta y arma los vals.
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
                dom.append(('company_id', '=', company.id))  # evita “de otra empresa”
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
    
            # ---- Resolver product.product de forma segura (evita _unknown) ----
            product_ref = False
            prod = l.producto_id
            Product = self.env['product.product']
            self._logger.debug("CFDI FLOW | LINE MAP | line_id=%s qty=%s price=%s iva=%.4f ieps=%.4f taxes=%s product_ref=%s",
                  l.id, l.cantidad, l.precio, l.iva_ratio, l.ieps_ratio, taxes, (product_ref and product_ref.id))
            if prod:
                # 1) Si tu modelo tiene helper explícito
                ensure = getattr(prod, 'ensure_product_product', None)
                if callable(ensure):
                    try:
                        pp = ensure()
                        if pp and pp._name == 'product.product':
                            product_ref = pp
                    except Exception:
                        pass
                    
                # 2) Si hay campo M2O product_id, leerlo con read() para evitar _unknown
                if not product_ref and 'product_id' in getattr(prod, '_fields', {}):
                    try:
                        val = prod.sudo().read(['product_id'])[0].get('product_id')
                        # val puede ser False, (id, name) o un recordset según la versión
                        if isinstance(val, (list, tuple)) and val:
                            product_ref = Product.browse(val[0])
                        elif getattr(val, 'id', False):
                            product_ref = val
                    except Exception:
                        product_ref = False
    
                # 3) Fallback por código interno
                if not product_ref:
                    code = getattr(prod, 'codigo', False) or getattr(prod, 'default_code', False)
                    if code:
                        product_ref = Product.search([('default_code', '=', str(code))], limit=1)
    
                # 4) Fallback por nombre
                if not product_ref:
                    pname = getattr(prod, 'name', False)
                    if pname:
                        product_ref = Product.search([('name', '=', pname)], limit=1)
    
            vals = {
                'name': l.descripcion or (getattr(prod, 'display_name', False) or 'Producto'),
                'quantity': l.cantidad or 0.0,
                'price_unit': l.precio or 0.0,
                'tax_ids': [(6, 0, taxes)] if taxes else False,
            }
            if product_ref and product_ref.exists():
                vals['product_id'] = product_ref.id
    
            cmds.append((0, 0, vals))
    
        return cmds

    #============================== Utils ==============================
    # Al crear línea UI: hereda empresa/cliente del padre si faltan, asume line_type='sale' por defecto,
    # intenta resolver producto por nombre y exige producto obligatorio.
    @api.model
    def create(self, vals):
        # Heredar empresa/cliente del padre si faltan (tu código actual) ...
        fact_id = vals.get('factura_id')
        if fact_id:
            parent = self.env['facturas.factura'].browse(fact_id)
            # --- BLOQUEO extra si intentan crear líneas directo en E ---
            if parent and parent.tipo == 'E':
                # Permitimos SOLO:
                # - prellenado inicial (egreso_prefill), o
                # - reemplazos coordinados (egreso_line_swap) hechos por Odoo (unlink+create)
                allowed = (self.env.context.get('egreso_prefill') or
                           self.env.context.get('egreso_line_swap'))
                if not allowed:
                    raise ValidationError(_('En Egresos no puedes agregar nuevas líneas.'))


            if not vals.get('empresa_id') and parent.empresa_id:
                vals['empresa_id'] = parent.empresa_id.id
            if not vals.get('cliente_id') and parent.cliente_id:
                vals['cliente_id'] = parent.cliente_id.id

            # EGRESO: si falta producto, tomar 1ro de la factura origen (tu lógica actual)
            if (not vals.get('producto_id')
                and parent.tipo == 'E'
                and parent.origin_factura_id
                and parent.origin_factura_id.line_ids):
                vals['producto_id'] = parent.origin_factura_id.line_ids[0].producto_id.id

        # 👇 respaldo: si no vino line_type, ponemos 'sale'
        if not vals.get('line_type'):
            vals['line_type'] = 'sale'

        # Tu búsqueda por nombre para producto (lo mantienes)
        if not vals.get('producto_id') and vals.get('descripcion'):
            Prod = self.env['productos.producto']
            p = Prod.search([('name', '=', vals['descripcion'])], limit=1)
            if p:
                vals['producto_id'] = p.id

        if not vals.get('producto_id'):
            raise ValidationError(_('Debes seleccionar un Producto/Servicio en la línea.'))

        return super().create(vals)

    # Postwrite de línea UI: auto-sana empresa/cliente desde el padre si quedaron vacíos.
    def write(self, vals):
        res = super().write(vals)
        # Auto-sanar registros existentes si quedaran sin empresa/cliente
        for r in self:
            if not r.empresa_id and r.factura_id and r.factura_id.empresa_id:
                r.empresa_id = r.factura_id.empresa_id.id
            if not r.cliente_id and r.factura_id and r.factura_id.cliente_id:
                r.cliente_id = r.factura_id.cliente_id.id
        return res
    
    # Mapea la línea UI a dicts “concepto” para el engine CFDI (clave SAT, unidad, descripción,
    # cantidades, valores, objeto de impuesto y tasas).
    def _to_cfdi_conceptos(self):
        conceptos = []
        for l in self:
            iva_factor = None
            # ejemplo: si iva_ratio == 0 puedes decidir basado en producto o UI
            if l.iva_ratio == 0.0:
                # setea 'Exento' o 'Tasa' según tu regla/UI
                iva_factor = getattr(l.producto_id, 'iva_factor', None)  # o desde la línea

            clave_sat = (getattr(l.producto_id.codigosat, 'code', '') or '').strip()
            clave_unidad = (getattr(l.producto_id, 'unidad', '') or '').strip()
            if not clave_sat:
                raise UserError(_("Línea %s: el producto '%s' no tiene Código SAT (campo 'codigosat').") % (l.id, l.producto_id.display_name))
            if not clave_unidad:
                raise UserError(_("Línea %s: el producto '%s' no tiene ClaveUnidad (campo 'unidad').") % (l.id, l.producto_id.display_name))


            conceptos.append({
                'clave_sat': (getattr(l.producto_id.codigosat, 'code', '') or '').strip(),
                'clave_unidad': (getattr(l.producto_id, 'unidad', '') or '').strip(),
                'no_identificacion': getattr(l.producto_id, 'codigo', None) or getattr(l.producto_id, 'default_code', None) or str(l.producto_id.id),
                'descripcion': l.descripcion or (getattr(l.producto_id, 'name', None) or l.producto_id.display_name or 'Producto'),
                'cantidad': l.cantidad or 1.0,
                'valor_unitario': l.precio or 0.0,
                'importe': round((l.cantidad or 0.0)*(l.precio or 0.0), 2),
                'objeto_imp': '02' if (l.iva_ratio or l.ieps_ratio or iva_factor) else '01',
                'iva': float(l.iva_ratio or 0.0),
                'ieps': float(l.ieps_ratio or 0.0),
                'iva_factor': iva_factor,   # 'Tasa' o 'Exento' si lo conoces
            })
        return conceptos

    # Tras timbrar: crea el vínculo ventas.transaccion.invoice.link por cada línea con transacción,
    # valida concurrencia (no sobre-facturar) y recomputa estado de facturación si aplica.
    def _touch_invoice_links(self, move):
        """Después de timbrar, registra enlace y vuelve a validar disponible (doble guarda)."""
        EPS = 1e-6
        Link = self.env['ventas.transaccion.invoice.link']
        created_links = 0
        
        for l in self.filtered(lambda x: x.transaccion_id):
            # En Odoo 18, usa SQL directo para el bloqueo si es necesario
            # O simplemente usa sudo() sin with_for_update()
            tx = l.transaccion_id.sudo()
            
            # Opción 1: Sin bloqueo explícito (más simple)
            qty = l.qty_to_invoice or l.cantidad or 0.0
            
            # Relee lo ya facturado (links abiertos)
            already = sum(tx.link_ids.filtered(lambda k: k.state != 'canceled').mapped('qty')) or 0.0
            total = tx.cantidad or 0.0
            
            if already + qty - EPS > total:
                raise ValidationError(_(
                    "Concurrencia: la transacción %s quedó sin disponible al timbrar. "
                    "Disponible: %.4f, intentando facturar: %.4f"
                ) % (tx.display_name, max(total - already, 0.0), qty))
            created_links += 1
            Link.create({
                'transaccion_id': tx.id,
                'move_id': move.id,
                'qty': qty,
                'state': 'open',
            })
            self._logger.info(
                "CFDI FLOW | LINKS | move_id=%s created=%s (solo líneas con transaccion_id)",
                move.id, created_links
            )
            # Verifica si el modelo tiene este método
            if hasattr(tx, '_recompute_invoice_status'):
                tx._recompute_invoice_status()

    # Constraint: evita crear/guardar líneas que excedan la cantidad disponible a facturar de la
    # transacción origen (considerando lo ya facturado).
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

    # Calcula subtotal, impuestos (IVA/IEPS) y total de la línea a partir de cantidad/precio/ratios.
    @api.depends('cantidad','precio','iva_ratio','ieps_ratio')
    def _calc_totals(self):
        for l in self:
            base = (l.cantidad or 0.0) * (l.precio or 0.0)
            l.subtotal = base
            l.iva_amount = round(base * (l.iva_ratio or 0.0), 2)
            l.ieps_amount = round(base * (l.ieps_ratio or 0.0), 2)
            l.total = round(base + l.iva_amount + l.ieps_amount, 2)

    @api.constrains('iva_ratio', 'ieps_ratio')
    def _check_tax_ratios(self):
        for l in self:
            for fld, val in (('IVA', l.iva_ratio), ('IEPS', l.ieps_ratio)):
                if val is not None and (val < 0 or val > 1):
                    raise ValidationError(_('El %s debe estar entre 0.0 y 1.0 (p.ej. 0.16).') % fld)



    # ============================== Fin utils ==============================