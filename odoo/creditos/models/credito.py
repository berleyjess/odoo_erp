# creditos/models/credito.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime
import logging
_logger = logging.getLogger(__name__)

class credito(models.Model):
    _name = 'creditos.credito'
    _description = 'Asignacion de contratos a clientes'
    _rec_name = 'label'
    
    currency_id = fields.Many2one(
        'res.currency', 
        string='Moneda',
        # Por defecto, toma la moneda de la compañía del usuario actual
        default=lambda self: self.env.company.currency_id.id,
        required=True
    )
    
    #Nomás para el _rec_name
    label = fields.Char(string="Folio", compute='_generate_label', store=True, default="Nuevo")

    cliente = fields.Many2one('clientes.cliente', string="Cliente", required=True)  
    contrato = fields.Many2one('contratos.contrato', string="Linea de crédito", required=True)  

    dictamen = fields.Selection(
        selection = [
            ('draft', 'Borrador'),
            ('check', 'En Comité'),
            ('confirmed', 'Aprobado'),
            ('discard', 'Rechazado'),
            ('bloked', 'Bloqueado')
        ], default='draft', string = "Estatus", compute='_nuevosuceso', store = True)
    
    entrys = fields.One2many('creditos.entry', 'contrato_id', "Registro de sucesos")

    cliente_estado_civil = fields.Selection(related='cliente.estado_civil', string="Estado Civil", readonly=True)
    cliente_conyugue = fields.Char(related='cliente.conyugue', string="Cónyuge", readonly=True)
    #ciclo = fields.Many2one('ciclos.ciclo', string="Ciclo", required=True)

    cargos = fields.One2many('cargosdetail.cargodetail', 'credito_id',string = "Cargos al Crédito")
    cargoscontrato = fields.One2many('cargosdetail.cargodetail', 'contrato_id', related = 'contrato.cargos', string = "Cargos del Contrato")

    ventas_ids = fields.One2many('ventas.venta', 'contrato', string = "Ventas al crédito")
    #pagos_ids = fields.One2many('pagos.pago', 'credito', string = "Pagos al crédito")

    bonintereses = fields.Float(string = "Bonificación de Intereses (0 - 1)", store = True, default = 0.0)
    primermovimiento = fields.Date(store = True, default = fields.Date.today)

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

    saldoporventas = fields.Monetary(string = "", compute='_saldoporventas', store=True)
    capital  = fields.Monetary(string = "", compute='_calc_interes', store=True)
    saldo = fields.Monetary(string ="Saldo", compute='_compute_saldo', store = False)
    interes = fields.Monetary(string = "Intereses", store = True, compute='_calc_interes', readonly = True)
    pagos = fields.Monetary(string="Pagos", default=0.0, store=True, readonly = True)
    monto = fields.Monetary(string="Financiamiento", digits=(12, 4), store = True, readonly = True, compute = '_calc_monto')

    predios = fields.One2many('creditos.predio', 'credito_id', string = "Predios")
    garantias = fields.One2many('creditos.garantia', 'credito_id', string = "Garantías")
    
    # Datos variables dependiendo del tipo de crédito
    vencimiento = fields.Date(string="Fecha de vencimiento del crédito",  default=fields.Date.today, store = True, readonly = True, compute = '_calc_vencimiento')
    superficie = fields.Float(string="Superficie Habilitada", digits=(12, 4), compute="_compute_superficie", store=True, readonly=True)

    usermonto = fields.Monetary(string = "Financiamiento", default = 0.0, store = True)
    uservencimiento = fields.Date(string="Fecha de vencimiento del crédito", required=True, default=fields.Date.today, store = False)
    usersuperficie = fields.Float(string="Superficie Habilitada", digits=(12, 4), store=True)

    obligado = fields.Char(string="Nombre", size=100)
    obligadodomicilio = fields.Many2one('localidades.localidad', string="Domicilio")
    obligadoRFC = fields.Char(string = "RFC")

    # Campo computed para validación de garantías
    total_garantias = fields.Monetary(string="Monto de Garantías", compute="_compute_total_garantias", store=False, readonly=True)
    
    folio = fields.Char(
        string="Folio",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _('Nuevo'),
        #help="Código único autogenerado con formato COD-000001"
    )

    @api.depends('entrys')
    def _nuevosuceso(self):
        for r in self:
            if r.entrys:
                ultimaentrada = fields.first(
                    r.entrys.sorted('id', reverse=True)[0]
                )
                if ultimaentrada.tipo == 'confirmed' or ultimaentrada.tipo == 'open':
                    r.dictamen = 'confirmed'
                elif ultimaentrada.tipo == 'discard':
                    r.dictamen = 'discard'
                elif ultimaentrada.tipo == 'bloked':
                    r.dictamen = 'blocked'
                elif ultimaentrada.tipo == 'draft':
                    r.dictamen = 'draft'
                elif ultimaentrada.tipo == 'check':
                    r.dictamen = 'check'

    @api.depends('cliente', 'contrato')
    def _generate_label(self):
        for record in self:
            if record.dictamen != 'confirmed' and record.dictamen != 'bloked':
                record.label = f"{record.folio}/{record.cliente.nombre}"
    
    @api.depends('dictamen')
    def _generate_folio(self):
        for record in self:
            if record.dictamen == 'confirmed':
                record.folio = self.env['ir.sequence'].next_by_code('creditos.folioaut') or _('Nuevo')


    @api.depends('capital', 'interes')
    def _compute_saldo(self):
        for record in self:
            record.saldo = record.capital + record.interes

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
                index = 0
                for cargo in record.cargoscontrato:
                    index += 1
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
                            'folio': 'CC#' + str(10000 + index)[-4:]
                        })
                record.recalc_cargos()

    def recalc_cargos(self): #Recalcula los montos de los cargos
        for record in self:
            total = sum(cargo.importe for cargo in record.cargos if cargo.credito_id.id==record.id and cargo.tipocargo in ('0','1','2'))
            saldo = total + record.saldoporventas
            for i in record.cargos:
                if i.tipocargo == '3':
                    i.total = (i.porcentaje * saldo)
                    total = total + i.importe
            #record.capital = total + record.saldoporventas
            record._calc_interes()

    @api.depends('pagos_ids', 'pagos_ids.state')
    def _calc_pagos(self):
        for record in self:
            record.pagos = sum(pago.importe for pago in record.pagos_ids if pago.credito.id==record.id and pago.state in ('posted'))
            record._calc_interes()


    @api.depends('ventas_ids', 'ventas_ids.state') #Agregar una venta para tomar la fecha del primer movimiento y la suma de ventas
    def _saldoporventas(self):
        for record in self:
            ufecha = self.env['ventas.venta'].search([('contrato', '=', record.id)], order='fecha desc', limit=1)
            if ufecha and ufecha.fecha and record.primermovimiento:
                if ufecha.fecha < record.primermovimiento:
                    record.primermovimiento = ufecha.fecha
            total = sum(venta.total for venta in record.ventas_ids if venta.state in ('confirmed', 'invoiced') and venta.contrato.id==record.id)
            record.saldoporventas = total
            record.recalc_cargos()

    @api.depends('cargos', 'cargoscontrato')#Agregar un cargo para tomar la fecha del primer movimiento
    def _addCargos(self):
        for record in self:
            ufecha = self.env['cargosdetail.cargodetail'].search([('contrato', '=', record.id)], order='fecha desc', limit=1)
            if ufecha and ufecha.fecha and record.primermovimiento:
                if ufecha.fecha < record.primermovimiento:
                    record.primermovimiento = ufecha.fecha
    
    def _calc_interes(self):
        for record in self:
            if record.tipocredito == '2':
                record.interes = 0.0
                continue
            #record.recalc_cargos()
            dia = record.primermovimiento
            today = fields.Date.today()
            record.interes = 0.0
            record.capital = 0.0
            record.pagos = 0.0
            while dia <= today:
                tasa = 0.18 - record.bonintereses # <--- LECTURA DE TASA DE INTERÉS MENSUAL CAPTURADA
                capitaldia = sum(record.cargos.importe for cargo in record.cargos if cargo.credito_id.id==record.id and cargo.fecha == dia)
                capitaldia += sum(record.cargoscontrato.importe for cargo in record.cargos if cargo.credito_id.id==record.id and cargo.fecha == dia and cargo.tipocargo in ('0','1','2'))
                if dia == today:
                    capitaldia += sum(record.cargoscontrato.importe for cargo in record.cargos if cargo.credito_id.id==record.id and cargo.fecha == dia and cargo.tipocargo == '3')
                capitaldia += sum(record.ventas_ids.importe for venta in record.ventas_ids if venta.contrato.id==record.id and venta.fecha == dia and venta.state in ('confirmed', 'invoiced'))
                #pagosdia = sum(record.pagos_ids.importe for pago in record.pagos_ids if pago.credito.id==record.id and pago.fecha == dia and pago.state in ('posted'))
                try:
                    pagosdia = sum(record.env['pagos.pago'].search([('credito', '=', record.id), ('fecha', '=', dia), ('status', '=', 'posted')]).mapped('monto'))
                except Exception as a:
                    pagosdia = 0.0
                    _logger.info("Error al referencia Pagos.pago, madafaca!")
                capitaldia -= pagosdia
                interesdia = capitaldia * tasa * (1/360)
                capitalizado = interesdia * tasa * (1/360)
                record.interes += interesdia + capitalizado
                record.capital = record.capital + capitaldia
                record.pagos = record.pagos + pagosdia
                dia = dia + timedelta(days=1)
            #if record.vencimiento > today:
            #    record.status = 'expired'
    
    @api.model
    def _cron_credito(self):
        try:
            for record in self:
                record._calc_interes()
            return True
        except Exception as e:
            _logger.error("Error en cron_credito: %s", e)
            return False

    FIELDS_TO_UPPER = ['obligado', 'obligadoRFC']

    @staticmethod
    def _fields_to_upper(vals, fields):
        for fname in fields:
            if fname in vals and isinstance(vals[fname], str):
                vals[fname] = vals[fname].upper()
        return vals

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
        # --- FORZAR MAYÚSCULAS ---
        vals = self._fields_to_upper(vals, self.FIELDS_TO_UPPER)
        return super(credito, self).create(vals)

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

    """@api.constrains('cliente', 'contrato')
    def _check_cliente_contrato_unico(self):
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
                    )"""

    """@api.constrains('garantias', 'usermonto', 'contrato')
    def _check_garantias_monto(self):
        for record in self:
            # CORREGIDO: Solo validar si el contrato requiere garantías (tipo AVIO - tipocredito == '0')
            if record.contrato and record.contrato.tipocredito == '0' and record.monto > 0:
                total_garantias = sum(garantia.valor for garantia in record.garantias if garantia.valor)
                if total_garantias < record.monto:
                    raise ValidationError(
                        f"El valor total de las garantías (${total_garantias:,.2f}) debe ser igual o mayor "
                        f"al monto del crédito (${record.monto:,.2f}).\n"
                        f"Faltan ${record.monto - total_garantias:,.2f} en garantías.
                    )"""
                
    """@api.constrains('superficie', 'contrato', 'predios')
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
                        raise ValidationError("Debes agregar al menos un predio con superficie cultivable mayor a 0.")"""
                    
    """@api.constrains('titularr')
    def _check_titular(self):
        for record in self:
            if not record.titularr and record.tipocredito != '2':
                raise ValidationError("El campo Titular es obligatorio para el predio.")"""

    @api.depends('predios.superficiecultivable', 'contrato', 'usersuperficie')
    def _compute_superficie(self):
        _logger.info(f"*/*/*/*/*/ CAMBIANDO LA SUPERFICIE */*/*/*/*/")
        for record in self:
            if record.contrato and record.contrato.tipocredito == '0':  # Solo para AVIO
                record.superficie = sum(p.superficiecultivable or 0.0 for p in record.predios)
            elif record.contrato and record.contrato.tipocredito == '1':  # Parcial
                record.superficie = record.usersuperficie
                _logger.info(f"*/*/*/*/*/ CAMBIANDO LA SUPERFICIE tipocredito={record.tipocredito}, superficie={record.superficie}, usersuperficie={record.usersuperficie} */*/*/*/*/")
    
    def action_entry_bloked(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.entry',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Bloquear contrato',
            'context': {
                'default_contrato_id': self.id,
                'default_tipo': 'bloked',
            } 
        }
    
    def action_entry_open(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.entry',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Habilitar contrato',
            'context': {
                'default_contrato_id': self.id,
                'default_tipo': 'open',
            } 
        }
    
    def action_entry_check(self):
        self.ensure_one()
        if self.monto <= 0:
            raise ValidationError("Debe incluir el <<Financiamiento>> solicitado antes de enviarlo a comité.")
        if self.superficie <= 0:
            raise ValidationError("En contrato debe especificar la <<Superficie>> que el cliente intenta habilitar.")
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.entry',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Enviar a comité',
            'context': {
                'default_contrato_id': self.id,
                'default_tipo': 'check',
            } 
        }
    
    def action_entry_draft(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.entry',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Sugerir correcciones',
            'context': {
                'default_contrato_id': self.id,
                'default_tipo': 'draft',
            } 
        }
    
    def action_entry_tech(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.entry',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Dictamen técnico',
            'context': {
                'default_contrato_id': self.id,
                'default_tipo': 'tech',
            } 
        }
    
    def action_entry_confirmed(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.entry',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Autorizar contrato',
            'context': {
                'default_contrato_id': self.id,
                'default_tipo': 'confirmed',
            } 
        }
    
    def action_entry_discard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'creditos.entry',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Rechazar contrato',
            'context': {
                'default_contrato_id': self.id,
                'default_tipo': 'discard',
            } 
        }

    #VER CARGOS RELACIONADAS
    def action_abrir_cargos(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cargos relacionados',
            'res_model': 'cargosdetail.cargodetail',
            'view_mode': 'list',
            'target': 'new',
            'context': {
                'default_credito_id': self.id,
            }
        }
    
    #VER VENTAS RELACIONADAS
    def action_abrir_ventas(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ventas relacionadas',
            'res_model': 'ventas.venta',
            'view_mode': 'list',
            'target': 'new',
            'context': {
                'default_contrato': self.id,
            }
        }
    
    #CARGAR ESTADO DE CUENTA
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
    
    #CARGAR GARANTÍAS
    def action_abrir_garantias(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Garantías',
            'res_model': 'creditos.garantia',
            'view_mode': 'list',
            'target': 'new',
            'context': {}
        }
    
        
    """#CARGAR PREDIOS
    def action_abrir_predios(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Predios',
            'res_model': 'creditos.predio',
            'view_mode': 'list',
            'target': 'new',
            'context': {
                'default_status': 'unlinked'
            }
        }"""
    
    
    #CARGAR REGISTRO DE EVENTOS
    def action_abrir_registro(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registro de sucesos',
            'res_model': 'creditos.entry',
            'view_mode': 'list',
            'target': 'new',
            'context': {
                'default_contrato_id': self.id
            }
        }
    
    def action_add_garantias(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Añadir Garantías',
            'res_model': 'creditos.garantia',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_credito_id': self.id
            }
        }
    

    def action_add_predios(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Añadir Predios',
            'res_model': 'creditos.predio',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_credito_id': self.id
            }
        }

    #def cargar_saldos(self):

    #MONTO NUNCA DEBE SER <= 0
    """_sql_constraints = [
        ('check_monto_positive', 'CHECK(monto > 0)', 'El monto solicitado no puede ser $0.'),
    ]"""

    #OBLIGADO SOLIDARIO ES REQUERIDO SI TIPOCREDITO != 2 Y SI NO ES EL TITULAR DEL CREDITO
    """@api.constrains('obligado', 'obligadorfc', 'obligadodomicilio')
    def _check_obligado_solidario(self):
        for rec in self:
            if rec.tipocredito != '2' and (not rec.titularr or rec.cliente_estado_civil == 'casado'):
                if not rec.obligado or not rec.obligadorfc or not rec.obligadodomicilio:
                    raise ValidationError(_('Debe ingresar los datos completos del obligado solidario del crédito.'))"""