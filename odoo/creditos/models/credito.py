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
        for proceso in self:
            if proceso.autorizaciones:
                _logger.info("*** ULTIMA AUTORIZACION ***")
                proceso.ultimaautorizacion = fields.first(
                    proceso.autorizaciones.sorted('id', reverse=True)[0]
                )
            else:
                # Si no hay autorizaciones, establecer como False o None
                proceso.ultimaautorizacion = False
    #Referencia el status de la última autorización capturada
    autorizada = fields.Selection(string="¿Está autorizada?", compute="_compute_autorizada", store=True,
        selection=[
            ('0', 'Pendiente'),
            ('1', 'Aprobado'),
            ('2', 'Rechazado')
        ], default='0')

    ultimaautorizacion_fecha = fields.Date(string = "Fecha", related = 'ultimaautorizacion.fecha', readonly = True, stored = True)
    ultimaautorizacion_descripcion = fields.Char(string = "Descripción", related = 'ultimaautorizacion.descripcion', readonly = True, stored = True)
    ultimaautorizacion_status = fields.Selection(string = "Status", related = 'ultimaautorizacion.status', readonly = True, stored = True)

    @api.depends('ultimaautorizacion')
    def _compute_autorizada(self):
        for record in self:
            _logger.info("*** AUTORIZACION AGREGADA ***")
            if record.ultimaautorizacion:
                record.autorizada = record.ultimaautorizacion.status
            else:
                record.autorizada = '0'

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

    @api.depends('activaciones')
    def _compute_ultima_activacion(self):
        for proceso in self:
            if proceso.activaciones:
                proceso.ultimaactivacion = fields.first(
                    proceso.activaciones.sorted('id', reverse=True)[0]
                )
            else:
                # Si no hay autorizaciones, establecer como False o None
                proceso.ultimaactivacion = False

    activacion = fields.Selection(string="¿Está autorizada?", related='ultimaactivacion.status', store=False,
    selection=[
        ('1', 'Aprobado'),
        ('0', 'Rechazado')
    ], default='0')

###########################################################################
##                      Otros Campos
###########################################################################


    cargos = fields.One2many('cargosdetail.cargodetail', 'credito_id',string = "Cargos al Crédito")

    #ventas_ids = fields.One2many('ventas.venta', 'contrato', string = "Ventas al crédito")

    contratoaprobado = fields.Boolean(string="Estado de Solicitud", readonly = True, compute='_checkautorizacionstatus', store = True)
    contratoactivo = fields.Boolean(string = "Estatus", readonly = True, compute='_checkcontratoactivo', store = True)

    cliente = fields.Many2one('clientes.cliente', string="Cliente", required=True)
    cliente_estado_civil = fields.Selection(related='cliente.estado_civil', string="Estado Civil", readonly=True)
    cliente_conyugue = fields.Char(related='cliente.conyugue', string="Cónyuge", readonly=True)
    #ciclo = fields.Many2one('ciclos.ciclo', string="Ciclo", required=True)
    contrato = fields.Many2one('contratos.contrato', string="Contrato", required=True)
    titularr = fields.Selection(
        selection=[
            ("0", "Sí"),
            ("1", "No")
        ], required = True, string="El cliente es responsable del crédito?", default="0"
    )

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
    monto = fields.Float(string="Monto solicitado", digits=(12, 4), required=True, store = True)
    vencimiento = fields.Date(string="Fecha de vencimiento", required=True, default=fields.Date.today, store = True)
    superficie = fields.Float(string="Superficie (Hectáreas)", digits=(12, 4), compute="_compute_superficie", store=True)

    obligado = fields.Char(string="Nombre", size=100, required=True)
    obligadodomicilio = fields.Many2one('localidades.localidad', string="Domicilio", required=True)
    obligadoRFC = fields.Char(string = "RFC", required=True)

    # Campo computed para validación de garantías
    total_garantias = fields.Float(string="Total Garantías", compute="_compute_total_garantias", store=False)

    
    folio = fields.Char(
        string='Folio',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _('Nuevo'),
        #help="Código único autogenerado con formato COD-000001"
    )

    is_editing = fields.Boolean(default=False, store = True)

    #def _generate_code(self):
    #    sequence = self.env['ir.sequence'].next_by_code('seq_credito_folio') or '/'
    #    number = sequence.split('/')[-1]
    #    return f"{number.zfill(6)}"
    
    
    @api.depends('ultimaautorizacion_status')
    def _checkautorizacionstatus(self):
        for record in self:
            record.contratoaprobado = record.ultimaautorizacion_status == '1' or record.ultimaautorizacion_status == 'Aprobado'
            _logger.info("*/*/*/*/*/*/ CONSULTANDO STATUS /*/*/*/*/*/* %s", record.contratoaprobado)

    @api.depends('ultimaactivacion_status', 'ultimaautorizacion_status')
    def _checkcontratoactivo(self):
        for record in self:
            record.contratoactivo = ((record.ultimaactivacion_status == '1' or not record.activaciones) and record.contratoaprobado == True)
            _logger.info("*/*/*/*/*/*/ CONSULTANDO HABILITACIÓN /*/*/*/*/*/* %s", record.contratoactivo)

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
        # Manejo de monto
        if vals.get('contrato') and not vals.get('monto'):
            contrato = self.env['contratos.contrato'].browse(vals['contrato'])
            if contrato.tipocredito != "2" and contrato.aporte and vals.get('superficie'):
                vals['monto'] = contrato.aporte * vals['superficie']
            elif not vals.get('monto'):
                vals['monto'] = 0.0
                
        # --- FORZAR MAYÚSCULAS ---
        vals = self._fields_to_upper(vals, self.FIELDS_TO_UPPER)
        return super(credito, self).create(vals)

    @api.onchange('contrato', 'superficie')
    def _onchange_monto(self):
        """Actualiza el monto basado en el tipo de crédito"""
        if self.contrato:
            if self.contrato.tipocredito == "2":  # Especial
                # Para crédito especial, se mantiene el monto manual
                if not self.monto:
                    self.monto = 0.0
            elif self.contrato.aporte and self.superficie:  # AVIO o Parcial
                # Para AVIO y Parcial, se calcula automáticamente
                self.monto = self.contrato.aporte * self.superficie
            else:
                self.monto = 0.0

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
        if self.titularr == '1' and self.cliente:  # Si el cliente es responsable
        #    self.obligado = self.cliente.nombre
            self.obligado = ''  # Limpia el campo para llenado manual
            self.obligadoRFC = '' # Limpia el RFC para llenado manual
        #    if hasattr(self.cliente, 'domicilio') and self.cliente.domicilio:
        #        self.obligadodomicilio = self.cliente.domicilio
        #    if hasattr(self.cliente, 'rfc') and self.cliente.rfc:
        #        self.obligadoRFC = self.cliente.rfc
        if self.titularr == '0' and self.cliente:  # Si el cliente SI es responsable
            # Auto-rellena con el cónyuge si está casado
            if (self.cliente.estado_civil in ['casado', 'union_libre'] and self.cliente.conyugue):
                self.obligado = self.cliente.conyugue
            else:
                self.obligado = ''  # Limpia el campo para llenado manual
                self.obligadoRFC = ''  # Limpia el RFC para llenado manual

    @api.depends('predios', 'contrato')
    def _depends_predios_superficie(self):
        # Si es tipo 1 permite edición manual
        if self.contrato and self.contrato.tipocredito == "1":
            return  # No actualiza automáticamente, el usuario puede escribir el valor
        # En cualquier otro tipo, actualiza automáticamente
        total_superficie = sum(predio.superficiecultivable or 0.0 for predio in self.predios)
        self.superficie = total_superficie

    """@api.onchange('ciclo')
    def _onchange_ciclo(self):
        #Maneja cambios en el ciclo
        if self.ciclo:
            # Asigna fecha de vencimiento si hay ciclo
            if self.ciclo.ffinal:
                self.vencimiento = self.ciclo.ffinal
            
            # Solo borra el contrato si realmente cambió el ciclo
            if self.contrato and hasattr(self.contrato, 'ciclo') and self.contrato.ciclo and self.contrato.ciclo.id != self.ciclo.id:
                self.contrato = False
            return {
                'domain': {'contrato': [('ciclo', '=', self.ciclo.id)]}
            }
        else:
            self.contrato = False
            self.vencimiento = False
            return {'domain': {'contrato': []}}
    """
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
            if record.cliente and record.contrato:
                existing = self.search([
                    ('cliente', '=', record.cliente.id),
                    ('contrato', '=', record.contrato.id),
                    ('id', '!=', record.id)
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

    @api.constrains('garantias', 'monto', 'contrato')
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
                    
    @api.constrains('titular')
    def _check_titular(self):
        for record in self:
            if not record.titular or not record.titular.strip():
                raise ValidationError("El campo Titular es obligatorio para el predio.")

    @api.depends('predios.superficiecultivable', 'contrato')
    def _compute_superficie(self):
        for record in self:
            if record.contrato and record.contrato.tipocredito == "0":  # Solo para AVIO
                record.superficie = sum(p.superficiecultivable or 0.0 for p in record.predios)
            # Si es tipo 1 o 2, se respeta el valor manual (no se calcula aquí)
    
    #BOTONES "Editar", "Guardar y Volver" y "Cancelar y volver a la lista"

    def action_editar(self):
        self.ensure_one()
        self.write({'is_editing': True})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.id,
            'view_mode': 'form',
            'target': 'current',  # 'new' lo muestra como popup/modal
        }

    
    def action_save_and_return(self):
        self.ensure_one()
        self.write({'is_editing': False})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.id,
            'view_mode': 'form',
            'target': 'current',  # 'new' lo muestra como popup/modal
        }
    
    
    def action_cancelar_y_volver(self):
    # Redirige a la lista de solicitudes de crédito (sin guardar cambios)
        self.ensure_one()
        self.write({'is_editing': False})
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'list',
            'target': 'current',  # 'new' lo muestra como popup/modal
        }

    creditoestatu_id = fields.Many2one(
        'creditoestatus.creditoestatu',
        string="Estatus de la Solicitud",
        help="Estado actual de la solicitud."
    )

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
    
    def action_autorizacion(self):
        """Acción para dictaminar la autorización de la solicitud de crédito."""
        self.ensure_one()
        """if not self.autorizaciones:
            raise ValidationError(_("No hay autorizaciones disponibles para esta solicitud."))"""
        
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

    def action_activacion(self):
        """Acción para dictaminar la activación de la solicitud de crédito."""
        self.ensure_one()
        """if not self.autorizaciones:
            raise ValidationError(_("No hay autorizaciones disponibles para esta solicitud."))"""
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.activacion',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Habilitar/Deshabilitar Contrato',
            'context': {
                'default_credito_id': self.id
            }
            
        }
    """
    def action_edocuenta(self):
        self.ensure_one()
        if not self.autorizaciones:
            raise ValidationError(_("No hay autorizaciones disponibles para esta solicitud."))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.cuentaxcobrar_ext',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Estado e cuenta',
            'context': {
                'default_credito_id': self.id
            }
            
        }
    """

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        _logger.info("**************************** ENTRADA A _get_view ******************************")

        if view_type == 'form' and not view_id:
            context = options.get('context', {})
            params = context.get('params', {})
            res_id = params.get('id')

            if not res_id:
                _logger.info("**************************** MODO CREACIÓN ******************************")
                #view = self.env.ref('creditos.view_credito_edit', raise_if_not_found=False)
            else:
                _logger.info("**************************** MODO EDICIÓN ******************************")
                #view = self.env.ref('creditos.view_credito_detail', raise_if_not_found=False)

            #if view:
            #   return super()._get_view(view.id, view_type, **options)

        return super()._get_view(view_id, view_type, **options)
    
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
