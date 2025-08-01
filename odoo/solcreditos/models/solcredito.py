# solcreditos/models/solcredito.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class solcredito(models.Model):
    _name = 'solcreditos.solcredito'
    _description = 'Asignacion de contratos a clientes'

    cliente = fields.Many2one('clientes.cliente', string="Nombre", required=True)
    cliente_nombre = fields.Char(string="Cliente", compute="_compute_cliente_nombre", store=False)
    cliente_estado_civil = fields.Selection(related='cliente.estado_civil', string="Estado Civil", readonly=True)
    cliente_conyugue = fields.Char(related='cliente.conyugue', string="Cónyuge", readonly=True)
    ciclo = fields.Many2one('ciclos.ciclo', string="Ciclo", required=True)
    contrato = fields.Many2one('contratos.contrato', string="Contrato", required=True)
    titularr = fields.Selection(
        selection=[
            ("0", "Sí"),
            ("1", "No")
        ], required = True, string="El cliente es responsable del crédito?", default="0"
    )

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

    predios = fields.One2many('solcreditos.predio_ext', 'solcredito_id', string = "Predios")
    garantias = fields.One2many('solcreditos.garantia_ext', 'solcredito_id', string = "Garantías")
    
    # Datos variables dependiendo del tipo de crédito
    monto = fields.Float(string="Monto solicitado", digits=(12, 4), required=True)
    vencimiento = fields.Date(string="Fecha de vencimiento", required=True, default=fields.Date.today)
    superficie = fields.Float(string="Superficie (Hectáreas)", digits=(12, 4), compute="_compute_superficie", store=True, )

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
        help="Código único autogenerado con formato COD-000001"
    )


    #def _generate_code(self):
    #    sequence = self.env['ir.sequence'].next_by_code('seq_solcredito_folio') or '/'
    #    number = sequence.split('/')[-1]
    #    return f"{number.zfill(6)}"
    
    @api.model
    def create(self, vals):
        """Asegura que siempre haya fecha de vencimiento y monto al crear"""
        if vals.get('folio', _('Nuevo')) == _('Nuevo'):
            vals['folio'] = self.env['ir.sequence'].next_by_code('solcreditos.folio') or _('Nuevo')
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
        return super(solcredito, self).create(vals)

    @api.depends('cliente')
    def _compute_cliente_nombre(self):
        """Compute para mostrar el nombre del cliente"""
        for record in self:
            record.cliente_nombre = record.cliente.nombre if record.cliente else ''

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

    @api.onchange('ciclo')
    def _onchange_ciclo(self):
        """Maneja cambios en el ciclo"""
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

    @api.onchange('contrato')
    def _onchange_contrato(self):
        """Maneja cambios en el contrato"""
        if self.contrato:
            # Si no hay ciclo seleccionado, lo asigna automáticamente
            if not self.ciclo and hasattr(self.contrato, 'ciclo') and self.contrato.ciclo:
                self.ciclo = self.contrato.ciclo
            
            # Asigna la fecha de vencimiento basada en el ciclo del contrato
            if hasattr(self.contrato, 'ciclo') and self.contrato.ciclo and self.contrato.ciclo.ffinal:
                self.vencimiento = self.contrato.ciclo.ffinal
            elif self.ciclo and self.ciclo.ffinal:
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