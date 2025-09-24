# creditos/models/credito.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class credito(models.Model):
    _name = 'creditos.credito'
    _description = 'Asignacion de contratos a clientes'
    _rec_name = 'contrato'

###########################################################################
##                      Dictámentes de Autorización
###########################################################################

    #Referencia a todas las autorizaciones relacionadas con esta solicitud
    autorizaciones = fields.One2many(
        'creditos.autorizacion',
        'credito_id',
        string='Autorizaciones',
    )

    #Apunta a la última autorización aprobada
    ultimaautorizacion = fields.Many2one('creditos.autorizacion', string = "Autorizado", compute='_compute_ultima_autorizacion', store=True)

    @api.depends('autorizaciones')
    def _compute_ultima_autorizacion(self):
        for r in self:
            if r.autorizaciones:
                _logger.info("*-*-*-*-*-* ULTIMA AUTORIZACION *-*-*-*-*-*")
                r.ultimaautorizacion = fields.first(
                    r.autorizaciones.sorted('id', reverse=True)[0]
                )
            else:
                # Si no hay autorizaciones, establecer como False o None
                r.ultimaautorizacion = False
            
            if r.ultimaautorizacion:
                if r.ultimaautorizacion_status == '1':
                    serie = "A"
                    if r.tipocredito == '1':
                        serie = "P"
                    else:
                        serie = "E"

                    r.dictamen = 'confirmed'
                    r.foliocredito= serie + self.env['ir.sequence'].next_by_code('creditos.folioaut')
                elif r.ultimaautorizacion_status == '0':
                    r.dictamen = 'draft'
                elif r.ultimaautorizacion_status == '2':
                    r.dictamen = 'cancelled'
                else:
                    r.dictamen = 'draft'

    ultimaautorizacion_fecha = fields.Date(string = "Fecha", related = 'ultimaautorizacion.fecha', readonly = True, stored = True)
    ultimaautorizacion_descripcion = fields.Char(string = "Descripción", related = 'ultimaautorizacion.descripcion', readonly = True, stored = True)
    ultimaautorizacion_status = fields.Selection(string = "Status", related = 'ultimaautorizacion.status', readonly = True, stored = True)

    
    dictamen = fields.Selection(
        selection = [
            ('draft', 'Borrador'),
            ('check', 'En Comité'),
            ('confirmed', 'Aprobado'),
            ('cancelled', 'Rechazado')
        ], default='draft', string = "Estatus", compute='_compute_ultima_autorizacion', store = True)
    
###########################################################################
##                      Cambio de Estatus
###########################################################################

    #Referencia a todas las autorizaciones relacionadas con esta solicitud
    activaciones = fields.One2many(
        'creditos.activacion',
        'credito_id',
        string='Activaciones',
        help='Activaciones relacionadas con esta solicitud de crédito.'
    )

    #Apunta a la última autorización aprobada
    ultimaactivacion = fields.Many2one('creditos.activacion', string = "Autorizado", compute='_compute_ultima_activacion', store = True)
    ultimaactivacion_fecha = fields.Date(string = "Fecha", related = 'ultimaactivacion.fecha', readonly = True, store = True)
    ultimaactivacion_descripcion = fields.Char(string = "Detalle", related = 'ultimaactivacion.descripcion', readonly = True, store = True)
    ultimaactivacion_status = fields.Selection(string = "Status", related = 'ultimaactivacion.status', readonly = True, store = True)

    status = fields.Selection(
        selection = [
            ('active', 'Activo'),
            ('paused', 'Pausado'),
            ('expired', 'Vencido'),
            ('exceeded', 'Excedido')
        ], default='active', string = "Estatus", compute='_compute_ultima_activacion', store = True)
    
    @api.depends('activaciones')
    def _compute_ultima_activacion(self):
        for r in self:
            if r.activaciones:
                r.ultimaactivacion = fields.first(
                    r.activaciones.sorted('id', reverse=True)[0]
                )
            else:
                # Si no hay autorizaciones, establecer como False o None
                r.ultimaactivacion = False

            if r.ultimaactivacion:
                if r.ultimaactivacion_status == '0' or r.dictamen != 'confirmed':
                    r.status = 'paused'
                elif r.ultimaactivacion_status == '1':
                    r.status = 'active'
                elif r.ultimaactivacion_status == "2":
                    r.status = 'expired'
                else:
                    r.status = 'active'

###########################################################################
##                      Otros Campos
###########################################################################
    cliente = fields.Many2one('clientes.cliente', string="Cliente", required=True)
    cliente_estado_civil = fields.Selection(related='cliente.estado_civil', string="Estado Civil", readonly=True)
    cliente_conyugue = fields.Char(related='cliente.conyugue', string="Cónyuge", readonly=True)
    #ciclo = fields.Many2one('ciclos.ciclo', string="Ciclo", required=True)
    contrato = fields.Many2one('contratos.contrato', string="Tipo de contrato", required=True)

    cargos = fields.One2many('cargosdetail.cargodetail', 'credito_id',string = "Cargos al Crédito")
    cargoscontrato = fields.One2many('cargosdetail.cargodetail', 'contrato_id', related = 'contrato.cargos', string = "Cargos del Contrato")

    #ventas_ids = fields.One2many('ventas.venta', 'contrato', string = "Ventas al crédito")

    bonintereses = fields.Float(string = "Bonificación de Intereses (0 - 1)", store = True, default = 0.0)
    
    @api.depends('bonintereses')
    def _check_bonificacion(self):
        for record in self:
            if record.bonintereses < 0 or record.bonintereses > 1:
                raise ValidationError("La bonificación de intereses debe estar entre 0 y 1.")
    
    @api.depends('contrato.cargos')
    def _gen_cargosbycontrato(self):
        self.env['cargosdetail.cargodetail'].search([
            ('credito_id', '=', self.id),
            ('cargocontrato', '=', True),
            ]).unlink()
        
        for record in self:
            if record.cargoscontrato:
                for cargo in record.cargoscontrato:
                    existing = self.env['cargosdetail.cargodetail'].search([
                        ('credito_id', '=', record.id),
                        ('cargo', '=', cargo.cargo.id),
                        ('cargocontrato', '=', True),
                    ])
                    if not existing:
                        self.env['cargosdetail.cargodetail'].create({
                            'credito_id': record.id,
                            'cargo': cargo.cargo.id,
                            'costo': cargo.costo,
                            'porcentaje': cargo.porcentaje,
                            'fecha': self.ultimaautorizacion_fecha or fields.Date.today(),
                            'cargocontrato': True,
                        })
                record.recalc_cargos()

    def recalc_cargos(self):
        for record in self:
            total = sum(cargo.importe for cargo in record.cargos if cargo.credito_id.id==record.id and cargo.tipocargo in ('0','1','2'))
            saldo = total + record.saldoporventas
            for i in record.cargos:
                if i.tipocargo == '3':
                    i.total = (i.porcentaje * saldo)
                    total = total + i.importe
            record.saldoejercido = total + record.saldoporventas

    fechaacomite = fields.Date(string="Fecha a Comité", required = False)

    tipocredito = fields.Selection(
        selection = [
            ('0', "AVIO"),
            ('1', "Parcial"),
            ('2', "Especial")
        ], default = '0', related = 'contrato.tipocredito', string = "Tipo de crédito", readonly = True
    )

    titularr = fields.Boolean(
        required = True, string="El cliente es responsable del crédito?", default=True, store = True
    )

    saldoporventas = fields.Float(string = "", compute="_calc_saldoporventas", store=True)
    saldoejercido  = fields.Float(string = "", compute="_saldoejercido", store=True)

    @api.depends('ventas_ids', 'ventas_ids.state')
    def _saldoporventas(self):
        for record in self:
            total = sum(venta.total for venta in record.ventas_ids if venta.state in ('confirmed', 'invoiced') and venta.contrato.id==record.id)
            record.saldoporventas = total
            record.recalc_cargos()
    """
    @api.depends('contrato.cargos', 'cargos', 'saldoporventas', 'saldoporventas')
    def _saldoejercido(self):
        for record in self:
            total = sum(cargo.importe for cargo in record.cargos if cargo.credito_id.id==record.id and cargo.tipocargo in ('0','1','2'))
            saldo = total + record.saldoporventas
            for i in record.cargos:
                if i.tipocargo == '3':
                    total = total + (i.porcentaje * saldo)
            record.saldoejercido = total + record.saldoporventas
    """
    def _calc_saldoporventas(self):
        for r in self:
            if 'ventas.venta' in self.env:
                ventas = self.env['ventas.venta'].search([('contrato', '=', r.id)])
                r.saldoporventas = sum(venta.total for venta in ventas if venta.state in ('confirmed', 'invoiced'))
            else:
                r.saldoporventas = 0.0

    """
    saldoejercido = fields.Float(string = "Saldo ejercito", store = False, compute = 'calc_saldosalidas')

    @api.depends('venta_ids.total', 'venta_ids.state')
    def _compute_saldo_ejercido(self):
        for record in self:
            # Suma el total de todas las ventas confirmadas ligadas a este crédito
            total = sum(venta.total for venta in record.venta_ids if venta.state in ('confirmed', 'invoiced'))
            record.saldo_ejercido = total
    """
    """edodecuenta = fields.One2many('cuentasxcobrar.cuentaxcobrar', 'contrato_id', string="Estado de cuenta")
    intereses = fields.Float(string = "Intereses", compute = '_calc_intereses', store = False)

    descintereses = fields.Float(string = "Descuento de Intereses", store = True, default = 0.0, required = True)

    def _calc_intereses(self):
        interes = 0
        tot_interes = 0
        lastdate = False
        capital = 0
        tasa = 0
        saldo = 0
        for cta in self.edodecuenta:
            if lastdate != False and lastdate != cta.fecha:
                interes = capital * (1 / 360) * tasa
                tot_interes += interes
            lastdate = cta.fecha
            periodo = self._periodo(cta.fecha)
            tasa = self.obtener_tasa(periodo)
            saldo = cta.saldo
            capital += saldo + interes
        interes = capital * (1 / 360) * tasa
        tot_interes += interes
        capital += saldo + interes

        self.intereses = tot_interes
    
    def obtener_tasa(self, periodo):
        tasa = self.env['tasaintereses'].search([
            ('periodo', '==', periodo),
        ], order='fecha DESC', limit=1)
        return tasa.tasa if tasa else 0.0

    @staticmethod
    def _periodo(fecha_date):
        return f"{fecha_date.month:02d}{str(fecha_date.year)[-2:]}"
    """

    FIELDS_TO_UPPER = ['obligado', 'obligadoRFC']

    @staticmethod
    def _fields_to_upper(vals, fields):
        for fname in fields:
            if fname in vals and isinstance(vals[fname], str):
                vals[fname] = vals[fname].upper()
        return vals

    tipocredito_val = fields.Char(compute="_compute_tipocredito_val", store=False)

    @api.depends('contrato')
    def _compute_tipocredito_val(self):
        for rec in self:
            rec.tipocredito_val = rec.contrato.tipocredito or ''

    predios = fields.One2many('creditos.predio_ext', 'credito_id', string = "Predios")
    garantias = fields.One2many('creditos.garantia_ext', 'credito_id', string = "Garantías")
    
    # Datos variables dependiendo del tipo de crédito
    monto = fields.Float(string="Monto solicitado", digits=(12, 4), store = True, readonly = True, compute = '_calc_monto')
    vencimiento = fields.Date(string="Fecha de vencimiento",  default=fields.Date.today, store = True, readonly = True, compute = '_calc_vencimiento')
    superficie = fields.Float(string="Superficie (Hectáreas)", digits=(12, 4), compute="_compute_superficie", store=True, readonly=True)

    usermonto = fields.Float(string = "Monto Solicitado", default = 0.0, store = True)
    uservencimiento = fields.Date(string="Fecha de vencimiento", required=True, default=fields.Date.today, store = False)
    usersuperficie = fields.Float(string="Superficie (Hectáreas)", digits=(12, 4), store=True)

    obligado = fields.Char(string="Nombre", size=100)
    obligadodomicilio = fields.Many2one('localidades.localidad', string="Domicilio")
    obligadoRFC = fields.Char(string = "RFC")

    # Campo computed para validación de garantías
    total_garantias = fields.Float(string="Total Garantías", compute="_compute_total_garantias", store=False)
    
    folio = fields.Char(
        string="Solicitud",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _('Nuevo'),
        #help="Código único autogenerado con formato COD-000001"
    )

    foliocredito = fields.Char(string="Contrato", readonly=True, store=True)

    @api.model
    def create(self, vals):
        #self.ensure_one()
        """Asegura que siempre haya fecha de vencimiento y monto al crear"""
        #vals['is_editing'] = True
        
        if vals.get('folio', _('Nuevo')) == _('Nuevo'):
            vals['folio'] = self.env['ir.sequence'].next_by_code('creditos.folio') or _('Nuevo')
        # Manejo de fecha de vencimiento
        if not vals.get('vencimiento'):
            if vals.get('ciclo'):
                ciclo = self.env['ciclos.ciclo'].browse(vals['ciclo'])
                if ciclo.ffinal:
                    vals['vencimiento'] = ciclo.ffinal
            elif vals.get('contrato'):
                contrato = self.env['contratos.contrato'].browse(vals['contrato'])
                if hasattr(contrato, 'ciclo') and contrato.ciclo and contrato.ciclo.ffinal:
                    vals['vencimiento'] = contrato.ciclo.ffinal        
        """
        # Manejo de monto
        if vals.get('contrato') and not vals.get('monto'):
            contrato = self.env['contratos.contrato'].browse(vals['contrato'])
            if contrato.tipocredito != '2' and contrato.aporte and vals.get('superficie'):
                vals['monto'] = contrato.aporte * vals['superficie']
            elif contrato.tipocredito=='2':
                vals['monto'] = vals['usermonto']
            elif not vals.get('monto'):
                vals['monto'] = 0.0
        """
        # --- FORZAR MAYÚSCULAS ---
        vals = self._fields_to_upper(vals, self.FIELDS_TO_UPPER)
        return super(credito, self).create(vals)

    """@api.onchange('contrato', 'superficie')
    def _onchange_monto(self):
        if self.contrato:
            if self.contrato.tipocredito != '2':  # Especial
                # Para crédito especial, se mantiene el monto manual
                if not self.monto:
                    self.monto = 0.0
            elif self.contrato.aporte and self.superficie:  # AVIO o Parcial
                # Para AVIO y Parcial, se calcula automáticamente
                self.monto = self.contrato.aporte * self.superficie
            else:
                self.monto = 0.0
    """

    @api.depends('garantias.valor')
    def _compute_total_garantias(self):
        """Calcula el total del valor de las garantías"""
        for record in self:
            record.total_garantias = sum(garantia.valor for garantia in record.garantias if garantia.valor)

    @api.onchange('cliente')
    def _onchange_cliente(self):
        """Auto-rellena campos basados en el cliente seleccionado"""
        if self.cliente:
            # Auto-rellena el obligado con el cónyuge si está casado
            if (self.cliente.estado_civil in ['casado', 'union_libre'] and 
                self.cliente.conyugue):
                self.obligado = self.cliente.conyugue
            #else:
                # Si no está casado o no tiene cónyuge, usa el nombre del cliente
            #    self.obligado = self.cliente.nombre  # CORREGIDO: era self.cliente.conyugue
            
            # Auto-rellena otros campos del cliente si existen
            #if hasattr(self.cliente, 'domicilio') and self.cliente.domicilio:
            #    self.obligadodomicilio = self.cliente.domicilio
            #if hasattr(self.cliente, 'rfc') and self.cliente.rfc:
            #    self.obligadoRFC = self.cliente.rfc

    @api.onchange('titularr', 'cliente')
    def _onchange_titularr(self):
        """Auto-rellena los datos del obligado solidario cuando el cliente es responsable"""
        if not self.titularr and self.cliente:  # Si el cliente es responsable
        #    self.obligado = self.cliente.nombre
            self.obligado = ''  # Limpia el campo para llenado manual
            self.obligadoRFC = '' # Limpia el RFC para llenado manual
        #    if hasattr(self.cliente, 'domicilio') and self.cliente.domicilio:
        #        self.obligadodomicilio = self.cliente.domicilio
        #    if hasattr(self.cliente, 'rfc') and self.cliente.rfc:
        #        self.obligadoRFC = self.cliente.rfc
        if self.titularr and self.cliente:  # Si el cliente SI es responsable
            # Auto-rellena con el cónyuge si está casado
            if (self.cliente.estado_civil in ['casado', 'union_libre'] and self.cliente.conyugue):
                self.obligado = self.cliente.conyugue
            else:
                self.obligado = ''  # Limpia el campo para llenado manual
                self.obligadoRFC = ''  # Limpia el RFC para llenado manual
    """
    @api.depends('predios', 'contrato', 'usersuperficie')
    def _depends_predios_superficie(self):
        _logger.info(f"*/*/*/*/*/ CAMBIANDO LA SUPERFICIE */*/*/*/*/")
        self.tipocredito = self.contrato.tipocredito if self.contrato else False
        # Si es tipo 1 permite edición manual
        
        if self.contrato and self.contrato.tipocredito == "1":
            return  # No actualiza automáticamente, el usuario puede escribir el valor
        
        # En cualquier otro tipo, actualiza automáticamente
        total_superficie = sum(predio.superficiecultivable or 0.0 for predio in self.predios)
        if self.tipocredito == '0':
            self.superficie = total_superficie
        elif self.tipocredito == '1':
            self.superficie = self.usersuperficie
            _logger.info(f"*/*/*/*/*/ CAMBIANDO LA SUPERFICIE tipocredito={self.tipocredito}, superficie={self.superficie}, usersuperficie={self.usersuperficie} */*/*/*/*/")
    """
    @api.depends('predios', 'contrato', 'superficie', 'usermonto')
    def _calc_monto(self):
        for r in self:
            if r.tipocredito == '0' or r.tipocredito == '1': 
                r.monto = r.superficie * r.contrato.aporte if r.contrato and r.contrato.aporte else 0.0
            elif r.tipocredito == '2':
                r.monto = r.usermonto

    @api.depends('contrato', 'uservencimiento')
    def _calc_vencimiento(self):
        for r in self:
            if r.contrato and r.tipocredito != '2':
                r.vencimiento = r.contrato.ciclo.ffinal
            else:
                r.vencimiento = r.uservencimiento

    @api.onchange('contrato')
    def _onchange_contrato(self):
        """Maneja cambios en el contrato"""
        if self.contrato:
            # Si no hay ciclo seleccionado, lo asigna automáticamente
            #if not self.ciclo and hasattr(self.contrato, 'ciclo') and self.contrato.ciclo:
            #    self.ciclo = self.contrato.ciclo
            
            # Asigna la fecha de vencimiento basada en el ciclo del contrato
            if hasattr(self.contrato, 'ciclo') and self.contrato.ciclo and self.contrato.ciclo.ffinal:
                self.vencimiento = self.contrato.ciclo.ffinal
            elif self.ciclo.ffinal:#elif self.ciclo and self.ciclo.ffinal:
                self.vencimiento = self.ciclo.ffinal

    @api.constrains('cliente', 'contrato')
    def _check_cliente_contrato_unico(self):
        """Validación: Un cliente no puede tener el mismo contrato"""
        for record in self:
            if self.tipocredito == '2':
                self.titularr = True
            
            if record.cliente and record.contrato:
                existing = self.search([
                    ('cliente', '=', record.cliente.id),
                    ('contrato', '=', record.contrato.id),
                    ('id', '!=', record.id),
                ])
                if existing:
                    # Usar display_name, o construir un nombre descriptivo
                    try:
                        contrato_name = record.contrato.display_name
                    except:
                        # Fallback: construir nombre usando campos disponibles
                        tipo_dict = {'0': 'AVIO', '1': 'Parcial', '2': 'Especial'}
                        tipo_nombre = tipo_dict.get(record.contrato.tipocredito, record.contrato.tipocredito)
                        contrato_name = f"Contrato {tipo_nombre} - Ciclo {record.contrato.ciclo.display_name if record.contrato.ciclo else 'N/A'}"
                    
                    raise ValidationError(
                        f"El cliente {record.cliente.nombre} ya tiene asignado el contrato {contrato_name}. "
                        "Un cliente no puede tener el mismo contrato más de una vez."
                    )

    @api.constrains('garantias', 'usermonto', 'contrato')
    def _check_garantias_monto(self):
        """Validación: El total de garantías debe ser igual o mayor al monto del crédito"""
        for record in self:
            # CORREGIDO: Solo validar si el contrato requiere garantías (tipo AVIO - tipocredito == '0')
            if record.contrato and record.contrato.tipocredito == '0' and record.monto > 0:
                total_garantias = sum(garantia.valor for garantia in record.garantias if garantia.valor)
                if total_garantias < record.monto:
                    raise ValidationError(
                        f"El valor total de las garantías (${total_garantias:,.2f}) debe ser igual o mayor "
                        f"al monto del crédito (${record.monto:,.2f}).\n"
                        f"Faltan ${record.monto - total_garantias:,.2f} en garantías."
                    )
                
    @api.constrains('superficie', 'contrato', 'predios')
    def _check_superficie_required(self):
        for record in self:
            if record.contrato:
                if record.contrato.tipocredito == '1':
                    # Editable, el usuario debe capturar
                    if not record.superficie or record.superficie <= 0:
                        raise ValidationError("Debes capturar la Superficie (Hectáreas) para este tipo de crédito.")
                elif record.contrato.tipocredito == '0':  # Solo para AVIO
                    # Se espera que sea suma de predios
                    total = sum(p.superficiecultivable or 0.0 for p in record.predios)
                    if not total or total <= 0:
                        raise ValidationError("Debes agregar al menos un predio con superficie cultivable mayor a 0.")
                    
    @api.constrains('titularr')
    def _check_titular(self):
        for record in self:
            if not record.titularr and record.tipocredito != '2':
                raise ValidationError("El campo Titular es obligatorio para el predio.")

    @api.depends('predios.superficiecultivable', 'contrato', 'usersuperficie')
    def _compute_superficie(self):
        _logger.info(f"*/*/*/*/*/ CAMBIANDO LA SUPERFICIE */*/*/*/*/")
        for record in self:
            if record.contrato and record.contrato.tipocredito == '0':  # Solo para AVIO
                record.superficie = sum(p.superficiecultivable or 0.0 for p in record.predios)
            elif record.contrato and record.contrato.tipocredito == '1':  # Parcial
                record.superficie = record.usersuperficie
                _logger.info(f"*/*/*/*/*/ CAMBIANDO LA SUPERFICIE tipocredito={record.tipocredito}, superficie={record.superficie}, usersuperficie={record.usersuperficie} */*/*/*/*/")
    
    #BOTONES "Editar", "Guardar y Volver" y "Cancelar y volver a la lista"

    def action_cambiar_a_habilitado(self):
        for rec in self:
            if rec.creditoestatu_id:
                rec.creditoestatu_id.action_habilitar()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_cambiar_a_deshabilitado(self):
        for rec in self:
            if rec.creditoestatu_id:
                rec.creditoestatu_id.action_deshabilitar()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_enviaracomite(self):
        self.ensure_one()
        self.fechaacomite = fields.Date.today()
        self.dictamen = 'check'

    def action_borrador(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.autorizacion',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Solicitar correcciones',
            'context': {
                'default_credito_id': self.id,
                'default_status': '0',
            }
        }
    
    def action_autorizar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.autorizacion',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Autorizar solicitud de crédito',
            'context': {
                'default_credito_id': self.id,
                'default_status': '1',
            }
        }
    
    def action_rechazar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.autorizacion',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Rechazar solicitud de crédito',
            'context': {
                'default_credito_id': self.id,
                'default_status': '2',
            }
        }

    """    # Lógica para enviar la solicitud al comité
    def action_autorizacion(self):
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.autorizacion',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Autorización de Contrato',
            'context': {
                'default_credito_id': self.id
            }
            
        }
    """

    def action_desbloquear(self):
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.activacion',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Desbloquear crédito',
            'context': {
                'default_credito_id': self.id,
                'default_status': '1',
            }
            
        }
    
    def action_bloquear(self):
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.activacion',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Bloquear crédito',
            'context': {
                'default_credito_id': self.id,
                'default_status': '0',
            }
            
        }
    
    def action_abrir_edocta(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Estado de Cuenta',
            'res_model': 'transient.edocta',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_justcacl': False,
                'default_contrato_id': self.id,
                'default_desde': fields.Date.today(),
                'default_hasta': fields.Date.today(),
            }
        }

    #def cargar_saldos(self):

    #MONTO NUNCA DEBE SER <= 0
    _sql_constraints = [
        ('check_monto_positive', 'CHECK(monto > 0)', 'El monto solicitado no puede ser $0.'),
    ]

    #OBLIGADO SOLIDARIO ES REQUERIDO SI TIPOCREDITO != 2 Y SI NO ES EL TITULAR DEL CREDITO
    @api.constrains('obligado', 'obligadorfc', 'obligadodomicilio')
    def _check_obligado_solidario(self):
        for rec in self:
            if rec.tipocredito != '2' and (not rec.titularr or rec.cliente_estado_civil == 'casado'):
                if not rec.obligado or not rec.obligadorfc or not rec.obligadodomicilio:
                    raise ValidationError(_('Debe ingresar los datos completos del obligado solidario del crédito.'))