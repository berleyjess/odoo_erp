# models/factura.py
# objeto interfaz + líneas + enlaces a origen
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)
import base64

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
    # compañía Odoo (de empresa, si existe; si no, de usuario)
    company_id = fields.Many2one(
        'res.company', string='Compañía Odoo',
        related='empresa_id.res_company_id', store=True, readonly=True, index=True
    )


    cliente_id = fields.Many2one('clientes.cliente', string='Cliente', index=True, ondelete='set null')
    tipo         = fields.Selection([('I','Ingresos'),('E','Egresos'),('P','Pago')], default='I', required=True)
    egreso_tipo = fields.Selection(
        [('nc', 'Nota de crédito'), ('dev', 'Devolución')],
        string='Tipo de egreso',
        default='nc'
    )
    uso_cfdi = fields.Selection(
        [('G03','G03'),('S01','S01'),('G02', 'G02')],
        string='Uso CFDI',
        required=True,
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

    # ========= Construcción de la factura contable + timbrado =========
#Valida consistencia (_check_consistency), construye el account.move en la compañía fiscal de la empresa (_build_account_move) y luego llama a _stamp_move_with_engine.    
    def action_build_and_stamp(self):
        for r in self:
            self._logger.info("CFDI FLOW | START | fact_id=%s tipo=%s empresa_id=%s company_id=%s cliente_id=%s",
                         r.id, r.tipo, r.empresa_id.id, r.company_id.id, r.cliente_id.id if r.cliente_id else None)
            try:
                if not r.cliente_id and not r.line_ids:
                    raise ValidationError(_("Selecciona un cliente en el encabezado o agrega al menos una línea con cliente."))
                r._check_consistency()
                move = r._build_account_move()
                self._logger.info("CFDI FLOW | MOVE | id=%s company_id=%s partner_id=%s lines=%s",
                             move.id, move.company_id.id, move.partner_id.id, len(move.invoice_line_ids))
                stamped = r._stamp_move_with_engine(move)
                self._logger.info("CFDI FLOW | STAMPED | uuid=%s", stamped.get('uuid'))
                r.write({'state':'stamped', 'uuid': stamped.get('uuid'), 'move_id': move.id})
                r.line_ids._touch_invoice_links(move)
            except Exception as e:
                self._logger.exception("CFDI FLOW | ERROR | fact_id=%s", r.id)  # stacktrace completo
                # deja rastro en el chatter
                try:
                    r.message_post(body="CFDI ERROR:<br/>%s" % (str(e) or repr(e)), subtype_xmlid="mail.mt_note")
                except Exception:
                    pass
                raise

    @api.model
    def _forma_pago_selection(self):
        # catálogo mínimo; si tienes modelo de catálogo, puedes poblarlo
        return [('01','Efectivo'),('03','Transferencia'),('04','TDC'),('28','TDD'),('99','Por definir')]

    @api.onchange('empresa_id')
    def _sync_companies(self):
        for r in self:
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
    #BOTÓN TIMBRAR: ----------------------------------------
#Resuelve partner_id a partir de tu clientes.cliente (con _ensure_partner_from_cliente).
#Crea la factura contable en la compañía fiscal (empresa_id.res_company_id), postea, e intenta mapear campos l10n (uso/metodo/forma).
    def _build_account_move(self):
        self.ensure_one()
        if not (self.empresa_id and self.empresa_id.res_company_id):   # ← fiscal
            raise ValidationError(_("Configura la 'Compañía fiscal (Odoo)' en la Empresa seleccionada."))

        partner = self._partner_from_context()
        if not partner:
            raise ValidationError(_('Falta cliente.'))

        forma = self.forma
        if self.tipo in ('I','E') and (self.metodo or '').upper() == 'PPD' and not forma:
            forma = '99'

        inv_company = self.empresa_id.res_company_id                   # ← crear el move en la fiscal
        lines_cmd = self.with_context(allowed_company_ids=[inv_company.id])\
                        .line_ids._to_move_line_cmds(inv_company)
    
        Move = self.env['account.move']\
            .with_company(inv_company)\
            .with_context(allowed_company_ids=[inv_company.id])

        mxn = self.env.ref('base.MXN', raise_if_not_found=False)
        move = Move.create({
            'move_type': 'out_invoice' if self.tipo == 'I' else 'out_refund',
            'partner_id': partner.id,
            'company_id': inv_company.id,
            'currency_id': (mxn.id if mxn else inv_company.currency_id.id),
            'invoice_origin': self.display_name,
            'invoice_date': fields.Date.context_today(self),
            'invoice_line_ids': lines_cmd,
        })
        move.action_post()

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
            map_mx_edi_fields(move, uso=self.uso_cfdi, metodo=self.metodo, forma=forma)
        except Exception:
            pass
        return move
    
    @api.onchange('tipo')
    def _onchange_tipo_force_pue(self):
        """Si es Egreso, siempre PUE (contado)."""
        for r in self:
            if r.tipo == 'E':
                r.metodo = 'PUE'   # solo método; no toco forma

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

    
    # ========= Validaciones clave =========
# Valida consistencia (primera accion en action_build_and_stamp)
    def _check_consistency(self):
        self.ensure_one()
        bad = self.line_ids.filtered(lambda l: l.sale_id and l.sale_id.sucursal_id != self.sucursal_id)
        super(FacturaUI, self)._check_consistency() if hasattr(super(), '_check_consistency') else None
        self.ensure_one()

        if not self.line_ids:
            raise ValidationError(_('Agrega al menos un concepto a la factura.'))
        if bad:
            raise ValidationError(_('Todas las transacciones deben pertenecer a la sucursal seleccionada.'))

        emp_ids = {l.empresa_id.id for l in self.line_ids if l.empresa_id}
        if len(emp_ids) > 1 or (self.empresa_id and emp_ids and self.empresa_id.id not in emp_ids):
            raise ValidationError(_('Todas las líneas deben pertenecer a la misma empresa.'))
        if self.empresa_id and not emp_ids:
            self.line_ids.write({'empresa_id': self.empresa_id.id})

        #super_exists = hasattr(super(), '_check_consistency')
        #if super_exists:
        #    super(FacturaUI, self)._check_consistency()
        #self.ensure_one()

        # Asegurar PUE en egresos (sin romper flujo)
        if self.tipo == 'E' and (self.metodo or '').upper() != 'PUE':
            self.metodo = 'PUE'

        # Egresos: validar cliente y factura origen
        if self.tipo == 'E':
            if not self.origin_factura_id:
                raise ValidationError(_('En un Egreso debes seleccionar la "Factura origen".'))
            if (self.origin_factura_id.cliente_id and self.cliente_id 
                and self.origin_factura_id.cliente_id.id != self.cliente_id.id):
                raise ValidationError(_('El cliente del Egreso debe coincidir con el de la factura origen.'))

        # << aquí el cambio >>
        clientes = {l.cliente_id.id for l in self.line_ids if l.cliente_id}
        if len(clientes) > 1:
            raise ValidationError(_('Todas las líneas deben ser del mismo cliente.'))

        if any(l.source_model == 'transacciones.transaccion' and l.sale_state == 'cancelled' for l in self.line_ids):
            raise ValidationError(_('Hay transacciones de ventas canceladas.'))

#Calcula conceptos desde tus líneas (line_ids._to_cfdi_conceptos()).
#Prepara extras (p.ej. InformacionGlobal para Público en General).
#Forza contexto a la compañía emisor fiscal y llama al servicio:

    def _stamp_move_with_engine(self, move):
        """Timbrar obligando el contexto de compañía del emisor fiscal (empresas.empresa)."""
        self.ensure_one()

        invoice_company = move.company_id
        emisor_company  = self._emisor_company(move)   # ← ahora en este modelo

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
            "CFDI FLOW | EMISOR | empresa=%s company=%s partner=%s zip='%s'",
            self.empresa_id.display_name, emisor_company.display_name,
            emisor_company.partner_id.display_name, (emisor_company.partner_id.zip or '')
        )

        # Validar ZIP de emisor (Lugar de expedición)
        zip_code = (emisor_company.partner_id.zip or '').strip()
        if not (zip_code.isdigit() and len(zip_code) == 5):
            raise ValidationError(_("Configura el C.P. (5 dígitos) en la compañía fiscal '%s'.") % emisor_company.display_name)
        # 🔒 (opcional) serializar timbrados por emisor y acotar espera por locks en adjuntos
        try:
            self.env.cr.execute("SELECT pg_advisory_xact_lock(%s)", [emisor_company.id])
        except Exception:
            pass
        self.env.cr.execute("SET LOCAL lock_timeout TO '30s'")

        if self.tipo == 'E' and (self.origin_factura_id and (self.origin_factura_id.uuid or '').strip()):
            extras.setdefault('relaciones', []).append({
                'tipo': '01',           # Nota de crédito
                'uuids': [self.origin_factura_id.uuid],
            })

         # Logs de diagnóstico útiles
        self._logger.info(
            "CFDI FLOW | ENGINE CONTEXT | company_invoice=%s company_fiscal=%s partner_fiscal=%s zip=%s",
            invoice_company.id, emisor_company.id, emisor_company.partner_id.id, zip_code
        )

        # Timbrar en el contexto de la compañía EMISOR (no la logueada)
        engine = (self.env['mx.cfdi.engine']
                .with_company(emisor_company)
                .with_context(allowed_company_ids=[emisor_company.id, invoice_company.id]))


        return engine.generate_and_stamp(
            origin_model='account.move',
            origin_id=move.id,
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

    # ========= Helpers =========
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
    
    # En FacturaUI._emisor_company
    def _emisor_company(self, move):
        self.ensure_one()
        emisor = self.empresa_id.res_company_id              # ← fiscal
        if not emisor:
            raise ValidationError(_("Configura la 'Compañía fiscal (Odoo)' en la Empresa seleccionada."))
        return emisor



    def _partner_from_context(self):
        # prioriza el del encabezado; si no, toma de líneas
        if self.cliente_id:
            return self._ensure_partner_from_cliente(self.cliente_id)
        for l in self.line_ids:
            if l.cliente_id:
                return self._ensure_partner_from_cliente(l.cliente_id)
        return False

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
    
    # --- Helper para clonar conceptos desde la factura origen ---
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
        nc = self.create({**nc_vals, 'line_ids': nc_lines})

        # Abrir la NC en formulario para revisar/ajustar (cantidades, etc.) y timbrar
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nota de crédito'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': nc.id,
            'target': 'current',
        }

    
    # ===== Botones para descargar/recuperar XML =====
    # Busca el attachment XML del CFDI (prioriza account.move, luego pagos, luego factura_ui, luego mx.cfdi.document)
    def _find_cfdi_xml_attachment(self):
        """Regresa attachment XML si existe (prioriza account.move → pagos → facturas.factura → mx.cfdi.document)."""
        self.ensure_one()
        Att = self.env['ir.attachment']

        # 1) Anexos del MOVE (preferido)
        if self.move_id:
            att = Att.search([
                ('res_model', '=', 'account.move'),
                ('res_id', '=', self.move_id.id),
                ('mimetype', '=', 'application/xml'),
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
                    ('mimetype', '=', 'application/xml'),
                ], limit=1, order='id desc')
                if att:
                    return att

        # 3) Fallback: adjunto en la propia FacturaUI
        att = Att.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('mimetype', '=', 'application/xml'),
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
                    ('mimetype', '=', 'application/xml'),
                ], limit=1, order='id desc')
                if att:
                    return att

        return self.env['ir.attachment']  # vacío


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


    def action_fetch_xml_from_sw(self):
        """Descarga el XML desde SW (PAC) y lo adjunta al move y a la FacturaUI; luego fuerza descarga."""
        self.ensure_one()
        if not self.uuid:
            raise ValidationError(_('No hay UUID para recuperar.'))

        # Usa exactamente el mismo proveedor que en ventas
        provider = self.env['mx.cfdi.engine']._get_provider()
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
    
    # =================== Egresos y pagos ========================
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        store=True, readonly=True
    )


    importe_total = fields.Monetary(string='Importe', currency_field='currency_id',
                                    compute='_compute_totales', store=True)
    saldo = fields.Monetary(string='Saldo', currency_field='currency_id',
                            compute='_compute_totales', store=True)

    # Egreso: relación obligatoria a la factura de Ingreso
    origin_factura_id = fields.Many2one(
        'facturas.factura',
        string='Factura origen',
        domain="[('tipo','=','I'), ('state','=','stamped'), \
                 ('empresa_id','!=', False), ('empresa_id','=', empresa_id), \
                 ('cliente_id','!=', False), ('cliente_id','=', cliente_id)]",
        copy=False,
        index=True,
    )

    origin_move_id = fields.Many2one(
        'account.move', string='Factura contable origen',
        related='origin_factura_id.move_id', store=True, readonly=True
    )

    @api.depends('line_ids.total', 'metodo', 'tipo')
    def _compute_totales(self):
        for r in self:
            r.importe_total = sum((l.total or 0.0) for l in r.line_ids)
            # Solo aplica a I/E como pediste
            if r.tipo in ('I', 'E'):
                r.saldo = r.importe_total if (r.metodo or '').upper() == 'PPD' else 0.0
            else:
                r.saldo = 0.0
    @api.onchange('cliente_id', 'empresa_id', 'origin_factura_id')
    def _onchange_origin_guard(self):
        if self.origin_factura_id and (
            (self.empresa_id and self.origin_factura_id.empresa_id != self.empresa_id) or
            (self.cliente_id and self.origin_factura_id.cliente_id != self.cliente_id)
        ):
            self.origin_factura_id = False




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


    def _to_cfdi_conceptos(self):
        conceptos = []
        for l in self:
            iva_factor = None
            # ejemplo: si iva_ratio == 0 puedes decidir basado en producto o UI
            if l.iva_ratio == 0.0:
                # setea 'Exento' o 'Tasa' según tu regla/UI
                iva_factor = getattr(l.producto_id, 'iva_factor', None)  # o desde la línea

            conceptos.append({
                'clave_sat': getattr(l.producto_id, 'sat_clave_prod_serv', None) or '',
                'clave_unidad': getattr(l.producto_id, 'sat_clave_unidad', None) or '',
                'no_identificacion': getattr(l.producto_id, 'default_code', None) or str(l.producto_id.id),
                'descripcion': l.descripcion or (l.producto_id.display_name or 'Producto'),
                'cantidad': l.cantidad or 1.0,
                'valor_unitario': l.precio or 0.0,
                'importe': round((l.cantidad or 0.0)*(l.precio or 0.0), 2),
                'objeto_imp': '02' if (l.iva_ratio or l.ieps_ratio or iva_factor) else '01',
                'iva': float(l.iva_ratio or 0.0),
                'ieps': float(l.ieps_ratio or 0.0),
                'iva_factor': iva_factor,   # 'Tasa' o 'Exento' si lo conoces
            })
        return conceptos


    def _touch_invoice_links(self, move):
        """Después de timbrar, registra enlace y vuelve a validar disponible (doble guarda)."""
        EPS = 1e-6
        Link = self.env['ventas.transaccion.invoice.link']
        
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
            
            Link.create({
                'transaccion_id': tx.id,
                'move_id': move.id,
                'qty': qty,
                'state': 'open',
            })
            
            # Verifica si el modelo tiene este método
            if hasattr(tx, '_recompute_invoice_status'):
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
            
    @api.model
    def create(self, vals):
        # Heredar empresa/cliente del padre si faltan (tu código actual) ...
        fact_id = vals.get('factura_id')
        if fact_id:
            parent = self.env['facturas.factura'].browse(fact_id)
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



    def write(self, vals):
        res = super().write(vals)
        # Auto-sanar registros existentes si quedaran sin empresa/cliente
        for r in self:
            if not r.empresa_id and r.factura_id and r.factura_id.empresa_id:
                r.empresa_id = r.factura_id.empresa_id.id
            if not r.cliente_id and r.factura_id and r.factura_id.cliente_id:
                r.cliente_id = r.factura_id.cliente_id.id
        return res
