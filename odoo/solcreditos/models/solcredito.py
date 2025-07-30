# solcreditos/models/solcredito.py
from odoo import models, fields, api
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

    predios = fields.One2many('solcreditos.predio_ext', 'solcredito_id', string = "Predios")
    garantias = fields.One2many('solcreditos.garantia_ext', 'solcredito_id', string = "Garantías")
    
    # Datos variables dependiendo del tipo de crédito
    monto = fields.Float(string="Monto solicitado", digits=(12, 4), required=True)
    vencimiento = fields.Date(string="Fecha de vencimiento", required=True, default=fields.Date.today)
    superficie = fields.Float(string="Superficie (Hectáreas)", digits=(12, 4), required=True)

    obligado = fields.Char(string="Titular del crédito", size=100, required=True)
    obligadodomicilio = fields.Many2one('localidades.localidad', string="Domicilio", required=True)
    obligadoRFC = fields.Char(string = "RFC", required=True)
    
    # Campo computed para validación de garantías
    total_garantias = fields.Float(string="Total Garantías", compute="_compute_total_garantias", store=False)

    @api.model
    def create(self, vals):
        """Asegura que siempre haya fecha de vencimiento y monto al crear"""
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
            else:
                # Si no está casado o no tiene cónyuge, usa el nombre del cliente
                self.obligado = self.cliente.conyugue
            
            # Auto-rellena otros campos del cliente si existen
            #if hasattr(self.cliente, 'domicilio') and self.cliente.domicilio:
             #   self.obligadodomicilio = self.cliente.domicilio
            #if hasattr(self.cliente, 'rfc') and self.cliente.rfc:
             #   self.obligadoRFC = self.cliente.rfc

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
                    raise ValidationError(
                        f"El cliente {record.cliente.nombre} ya tiene asignado el contrato {record.contrato.nombre}. "
                        "Un cliente no puede tener el mismo contrato más de una vez."
                    )

    @api.constrains('garantias', 'monto', 'contrato')
    def _check_garantias_monto(self):
        """Validación: El total de garantías debe ser igual o mayor al monto del crédito"""
        for record in self:
            # Solo validar si el contrato requiere garantías (no es tipo AVIO - tipocredito != '0')
            if record.contrato and record.contrato.tipocredito != '0' and record.monto > 0:
                total_garantias = sum(garantia.valor for garantia in record.garantias if garantia.valor)
                if total_garantias < record.monto:
                    raise ValidationError(
                        f"El valor total de las garantías (${total_garantias:,.2f}) debe ser igual o mayor "
                        f"al monto del crédito (${record.monto:,.2f}).\n"
                        f"Faltan ${record.monto - total_garantias:,.2f} en garantías."
                    )