# -*- coding: utf-8 -*-
"""
Modelo: clientes.cliente
Descripción: Administra la cartera de clientes para el módulo de Crédito.
Incluye datos fiscales, de identificación (INE, CURP), domicilio, estado civil y contactos
relacionados. Implementa lógica para:
- Autogenerar un código interno incremental.
- Forzar mayúsculas al crear/editar.
- Ajustar dinámicamente el dominio del régimen fiscal según el tipo de cliente.
- Limpiar el nombre del cónyuge cuando el estado civil no lo requiere.
"""
import re
from odoo.exceptions import ValidationError
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class cliente(models.Model):
    """
    Modelo principal de cliente.

    Notas:
    - El nombre técnico del modelo es `clientes.cliente`.
    - Utiliza una secuencia `seq_client_code` para generar el campo `codigo`.
    - Implementa `@api.onchange` para actualizar dominios y limpiar campos en la vista.
    - Sobrescribe `create` y `write` para normalizar datos a mayúsculas.
    """
    
    _name='clientes.cliente'  #Modelo.Cliente ("nombre del modulo"."nombre del modelo")
    _description='Cartera de clientes'
    _rec_name='nombre'  #Nombre del campo que se mostrará en las vistas de lista y búsqueda
    _inherits = {'persona.persona': 'persona_id'}
    _order = 'codigo'  #Orden por defecto en las vistas de lista
    
    codigo = fields.Char( #Código interno del Cliente
        string='Código',
        size=10,
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_code(),
        help="Código interno autogenerado (ej. 000001). Controlado por la secuencia 'seq_client_code'."
    )

    persona_id = fields.Many2one('persona.persona', required=True, ondelete='restrict', index=True, string="Persona")

    nombre = fields.Char(string="Nombre/Razón social", readonly=False, required=True,related='persona_id.name',store=False,help="Nombre completo o razón social del cliente.")

    rfc = fields.Char(string="RFC",size=13, readonly=False, required=False,related='persona_id.rfc',store=False, index=True, help="Registro Federal de Contribuyentes")

    #es_cliente = fields.Boolean(default=True, related='persona_id.es_cliente')

    # Constantes de validación de RFC
    # RFC_GENERICOS contiene RFCs genéricos que no deben ser validados estrictamente
    RFC_GENERICOS = ('XAXX010101000', 'XEXX010101000')
    # RFC_REGEX es una expresión regular que valida el formato estándar del RFC
    RFC_REGEX = re.compile(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$')  # Formato estándar SAT
    # Expresiones regulares para CURP e INE
    # CURP_REGEX valida el formato de la CURP según las reglas del SAT
    CURP_REGEX = re.compile(
    r'^[A-ZÑ][AEIOU][A-ZÑ]{2}'   # 4 letras iniciales
    r'\d{6}'                     # fecha: YYMMDD
    r'[HM]'                      # sexo
    r'[A-ZÑ]{2}'                 # entidad federativa
    r'[B-DF-HJ-NP-TV-ZÑ]{3}'     # consonantes internas
    r'[A-Z\d]\d$'                # homoclave y dígito verificador
    )

    INE_REGEX = re.compile(r'^[A-ZÑ]{6}\d{8}[A-ZÑ]\d{3}$')  # 18 caracteres
    CP_REGEX       = re.compile(r'^\d{5}$')

    tipo = fields.Selection(
        selection = [
            ("0", "Persona Física"),
            ("1", "Persona Moral")
        ], string="Tipo de Cliente", required=True, default = "0",
        help="Define si el cliente es Persona Física o Persona Moral. Afecta el dominio del campo Régimen Fiscal."
    )

    # related editables (escriben en persona.persona)
    email    = fields.Char(string="Email",readonly=False,related='persona_id.email', store=False)
    telefono = fields.Char(string="Teléfono", readonly=False,related='persona_id.telefono', store=False)

    rfc_has_existing_cliente = fields.Boolean(compute='_compute_rfc_has_existing', store=False)

    def _compute_rfc_has_existing(self):
        for rec in self:
            r = (rec.rfc or '').strip().upper()
            if not r:
                rec.rfc_has_existing_cliente = False
                continue
            p = self.env['persona.persona'].sudo().search([('rfc', '=', r)], limit=1)
            if not p:
                rec.rfc_has_existing_cliente = False
            else:
                rec.rfc_has_existing_cliente = bool(
                    self.env['clientes.cliente'].sudo().search_count([('persona_id', '=', p.id)])
                )

    def _get_contacto_ppal(self):
        self.ensure_one()
        # Preferir el marcado como principal; si no hay, toma el primero
        return self.contacto.filtered(lambda c: c.es_principal)[:1] or self.contacto[:1]

    @api.onchange('contacto')
    def _onchange_contacto_autofill(self):
        c = self._get_contacto_ppal()
        if c:
            self.email = c.email
            self.telefono = c.telefono

    def _sync_persona_from_contact(self):
        """Rellena telefono/email de persona.persona tomando el contacto principal.
           Solo completa si en persona están vacíos (no sobreescribe valores ya capturados)."""
        for rec in self:
            if not rec.persona_id:
                continue
            # usa el helper que ya tienes
            c = rec._get_contacto_ppal()
            if not c:
                continue
            updates = {}
            if c.telefono and not rec.persona_id.telefono:
                updates['telefono'] = c.telefono
            if c.email and not rec.persona_id.email:
                updates['email'] = (c.email or '').strip().lower()
            if updates:
                rec.persona_id.write(updates)




    regimen = fields.Many2one('clientes.c_regimenfiscal',
                              string = "Régimen Fiscal",
                              domain="[('tipo', 'in', [tipo == '0' and '0' or '1', '2'])]",
                              help="Régimen fiscal del cliente. El dominio se recalcula dinámicamente en _onchange_tipo."
    )

    codigop = fields.Char(string="Código Postal", size=5, readonly=False,related='persona_id.codigop',store=False)
    localidad = fields.Many2one('localidades.localidad', readonly=False,related='persona_id.localidad_id',store=False, string = "Ciudad/Localidad")
    calle = fields.Char(string = "Calle", size = 32, readonly=False,related='persona_id.calle', store=False) #FALTA PONER EN PERSONAS.PERSONA
    colonia      = fields.Char(string="Colonia", readonly=False,related='persona_id.colonia', store=False) #FALTA AGREGAR EN CLIENTE
    numero = fields.Char(string = "Número", readonly=False,related='persona_id.numero_casa',store=False)

    # Campos de identificación / Estado civil
    ine = fields.Char(string="INE (Clave de Elector)", size=18, help="Ingrese solo la clave de lector del INE")
    curp = fields.Char(string="CURP", size=18, help="Clave Única de Registro de Población")
    estado_civil = fields.Selection([
        ('soltero', 'Soltero(a)'),
        ('casado', 'Casado(a)'),
        ('divorciado', 'Divorciado(a)'),
        ('viudo', 'Viudo(a)'),
        ('union_libre', 'Unión Libre')
    ], string="Estado Civil"
    )

    conyugue = fields.Char(string="Nombre del Cónyuge", size=100, help="Nombre completo del cónyuge")

    regimenconyugal = fields.Selection(
        string = "Régimen Conyugal", store = True, selection = [
            ('0', "Sociedad Conyugal"),
            ('1', "Separación de Bienes"),
            ('2', "Régimen Mixto")
        ]
    )

    dependientes = fields.Integer(
        string = "Dependientes económicos", default = 0, store = True
    )

    tipovivienda = fields.Selection(
        string = "Tipo de Vivienda", store = True, selection = [
            ('0', "Propia"),
            ('1', "Alquiler")
        ]
    )
    
    #Referencias Laborales
    empresa = fields.Char(string = "Empresa donde labora", store = True, size = 32)
    puesto = fields.Char(string = "Puesto que desempeña", store = True)
    ingresomensual = fields.Float(string = "Ingreso Mensual Estimado", store = True, default = 0.0)

    #Relación con contactos

    contacto = fields.One2many('contactos.contacto', 'cliente_id', string = "Contactos",help="Contactos externos relacionados con este cliente.")

    # ONCHAGE METHODS

    """
        Actualiza el dominio del campo 'regimen' dependiendo del tipo de cliente.
        Además, muestra una advertencia si hay RFC capturado para que se valide
        coherencia con el tipo seleccionado.

        Retorna:
            dict: dominio dinámico para el campo 'regimen' y un warning opcional.
    """

    _sql_constraints = [
    ('cliente_codigo_unique', 'unique(codigo)', 'El código de cliente debe ser único.'),
    ('cliente_persona_unique','unique(persona_id)', 'Esta persona ya está registrada como cliente.'),
    ]

    
    # -----------------------------
    # Onchange: auto-rellenar por RFC
    # -----------------------------
    @api.onchange('rfc')
    def _onchange_rfc_autofill(self):
        """Si el RFC ya pertenece a una persona con cliente: NO enlazar persona y avisar.
           Si existe persona SIN cliente: enlaza persona para que se autocompleten los related."""
        r = (self.rfc or '').strip().upper()
        if not r or self.persona_id:
            return
        Person = self.env['persona.persona'].sudo()
        p = Person.search([('rfc', '=', r)], limit=1)
        if not p:
            return
        if self.env['clientes.cliente'].sudo().search_count([('persona_id', '=', p.id)]):
            return {
                'warning': {
                    'title': _('RFC ya registrado'),
                    'message': _('Ya existe un cliente con este RFC. Usa el botón "Buscar persona por RFC" para abrirlo.')
                }
            }
        self.persona_id = p.id



    def action_open_existing_by_rfc(self):
        self.ensure_one()
        r = (self.rfc or '').strip().upper()
        if not r:
            raise UserError(_("Captura el RFC para buscar."))
        p = self.env['persona.persona'].sudo().search([('rfc', '=', r)], limit=1)
        if not p:
            raise UserError(_("No existe una persona con el RFC %s.") % r)
        existing = self.env['clientes.cliente'].sudo().search([('persona_id', '=', p.id)], limit=1)
        if not existing:
            raise UserError(_("No existe cliente con ese RFC."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cliente existente'),
            'res_model': 'clientes.cliente',
            'view_mode': 'form',
            'res_id': existing.id,
            'target': 'current',
        }
  
    # Logica de negocio / hooks.

    def _generate_code(self):
        """
        Genera el código interno del cliente utilizando la secuencia 'seq_client_code'.
        Formatea el número a 6 dígitos con ceros a la izquierda.

        Returns:
            str: Código formateado, ej. '000001'
        """
        sequence = self.env['ir.sequence'].next_by_code('seq_client_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(6)}"
    
    @api.model
    def create(self, vals):
        # normaliza RFC
        r = (vals.get('rfc') or '').strip().upper()
        Person = self.env['persona.persona']
        # ---- Evitar duplicado antes del constraint ----
        pid = vals.get('persona_id')
        if pid and self.env['clientes.cliente'].sudo().search_count([('persona_id', '=', pid)]):
            raise ValidationError(_("Esta persona ya está registrada como cliente. Usa el botón 'Buscar persona por RFC' para abrirlo."))

        if not vals.get('persona_id'):
            if r:
                p = Person.search([('rfc', '=', r)], limit=1)
                if p:
                    # Reutiliza persona encontrada
                    # Si la persona ya tiene cliente, no permitas crear otro
                    if self.env['clientes.cliente'].sudo().search_count([('persona_id', '=', p.id)]):
                        raise ValidationError(_("Esta persona ya está registrada como cliente. Usa el botón 'Buscar persona por RFC' para abrirlo."))
                    vals['persona_id'] = p.id

                    # Opcional: completa SOLO vacíos en persona
                    to_fill = {}
                    for ck, pk in [
                        ('nombre','name'), ('email','email'), ('telefono','telefono'),('calle','calle'),('codigop','codigop'),
                        ('localidad','localidad_id'), ('colonia','colonia'), ('numero','numero_casa'),
                    ]:
                        if vals.get(ck) and not getattr(p, pk):
                            to_fill[pk] = vals[ck]
                    if to_fill:
                        p.write(to_fill)
                else:
                    # Crea persona con lo que venga del form de cliente
                    persona_vals = {
                        'name': vals.get('nombre'),
                        'rfc':  r,
                        'email': (vals.get('email') or '').strip().lower() if vals.get('email') else False,
                        'telefono': vals.get('telefono'),
                        'localidad_id': vals.get('localidad'),
                        'colonia': vals.get('colonia'),
                        'numero_casa': vals.get('numero'),
                        'calle': vals.get('calle'),
                        'codigop': vals.get('codigop'),
                        
                    }
                    vals['persona_id'] = Person.create(persona_vals).id
            else:
                # Sin RFC, crea persona mínima (si tu lógica lo permite)
                persona_vals = {
                    'name': vals.get('nombre'),
                    'email': (vals.get('email') or '').strip().lower() if vals.get('email') else False,
                    'telefono': vals.get('telefono'),
                    'localidad_id': vals.get('localidad'),
                    'colonia': vals.get('colonia'),
                    'numero_casa': vals.get('numero'),
                    'codigop': vals.get('codigop'),
                    
                }
                vals['persona_id'] = Person.create(persona_vals).id

        # Código por secuencia si no llegó
        if not vals.get('codigo'):
            seq = self.env['ir.sequence'].next_by_code('seq_client_code') or '/'
            vals['codigo'] = (seq.split('/')[-1]).zfill(6)

        rec = super().create(vals)
        rec._sync_persona_from_contact()
        return rec

    def write(self, vals):
        res = super().write(vals)
        # Si cambiaron líneas del O2M, o si cambió persona_id, sincroniza.
        if 'contacto' in vals or 'persona_id' in vals:
            self._sync_persona_from_contact()
        return res
    
    @api.constrains('rfc')
    def _check_unique_rfc(self):
        for rec in self:
            rfc = (rec.rfc or '').strip().upper()
            if rfc:
                es_generico = rfc in self.RFC_GENERICOS
                if not es_generico and not self.RFC_REGEX.fullmatch(rfc):
                    raise ValidationError("El RFC '%s' no cumple con el formato válido." % rfc)
                if not es_generico and rec.search_count([('rfc', '=', rfc), ('id', '!=', rec.id)]):
                    raise ValidationError("El RFC '%s' ya está registrado en otro cliente." % rfc)



    # ---------- CONSTRAINS ---------------------------------

    @api.constrains('rfc', 'tipo')
    def _check_rfc(self):
        for rec in self:
            rfc = (rec.rfc or '').strip().upper()
            if not rfc:
                raise ValidationError(_("El campo RFC es obligatorio."))

        # 1) Longitud según tipo
            if rec.tipo == '0' and len(rfc) != 13:
                raise ValidationError(_("Persona Física: el RFC debe tener 13 caracteres."))
            if rec.tipo == '1' and len(rfc) != 12:
                raise ValidationError(_("Persona Moral: el RFC debe tener 12 caracteres."))

        # 2) Formato y unicidad (salvo genéricos)
            es_generico = rfc in self.RFC_GENERICOS
            if not es_generico and not self.RFC_REGEX.fullmatch(rfc):
                raise ValidationError(_("El RFC '%s' no tiene un formato válido.") % rfc)

            if not es_generico and rec.search_count([('rfc', '=', rfc), ('id', '!=', rec.id)]):
                raise ValidationError(_("El RFC '%s' ya está registrado en otro cliente.") % rfc)


    #@api.constrains('curp')
    #def _check_curp(self):
    #    for rec in self:
    #        curp = (rec.curp or '').strip().upper()
    #        if curp and not self.CURP_REGEX.fullmatch(curp):
    #            raise ValidationError(_("La CURP '%s' no es válida.") % curp)


    #@api.constrains('ine')
    #def _check_ine(self):
    #    for rec in self:
    #        ine = (rec.ine or '').strip().upper()
    #        if ine and not self.INE_REGEX.fullmatch(ine):
    #            raise ValidationError(
    #                _("La clave de elector INE '%s' no es válida.") % ine
    #            )

    @api.constrains('estado_civil', 'conyugue', 'regimenconyugal')
    def _check_requeridos_conyugue(self):
        for record in self:
            if record.estado_civil in ['casado', 'union_libre']:
                if not record.conyugue:
                    raise ValidationError("¡El nombre del cónyuge es obligatorio!")
                if not record.regimenconyugal:
                    raise ValidationError("¡El régimen conyugal es obligatorio!")
            
    # ======= Tus onchanges/constraints originales que NO choquen con persona =======
    @api.onchange('tipo')
    def _onchange_tipo(self):
        if not self.tipo:
            self.regimen = False
            return {'domain': {'regimen': []}}
        domain_map = {'0': ['0','2'], '1': ['1','2']}
        return {'domain': {'regimen': [('tipo','in', domain_map.get(self.tipo, []))]}}

    @api.onchange('estado_civil')
    def _onchange_estado_civil(self):
        if self.estado_civil not in ['casado','union_libre']:
            self.conyugue = False

    CP_REGEX = re.compile(r'^\d{5}$')
    @api.constrains('codigop')
    def _check_cp(self):
        for rec in self:
            cp = (rec.codigop or '').strip()
            if cp and not self.CP_REGEX.fullmatch(cp):
                raise ValidationError(_("El Código Postal '%s' debe ser de 5 dígitos.") % cp)

    @api.constrains('numero')
    def _check_numero(self):
        for rec in self:
            if isinstance(rec.numero, str) and rec.numero and not rec.numero.isdigit():
                raise ValidationError(_("El número de calle solo puede contener dígitos."))

    def action_save(self):
        """
        Acción para guardar y volver a la vista de lista.
        Útil si pones un botón 'Guardar' manual en la vista.
        """
        self.ensure_one()
        
        # Retornar a la vista lista
        return {
            'type': 'ir.actions.act_window',
            'name': 'Clientes',
            'res_model': 'clientes.cliente',
            'view_mode': 'list,form',
            'target': 'current',
        }
    
    def action_editar(self):
        """Método que retorna la acción para abrir el registro en modo edición"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Editar Cliente',
            'res_model': 'clientes.cliente',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('clientes.view_clientes_form_edit').id,
            'target': 'current',
        }

    def open_record(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Detalle',
            'res_model': 'clientes.cliente',
            'view_mode': 'form',
            'view_id': self.env.ref('clientes.view_clientes_form').id,
            'target': 'new',
            'res_id': self.id,
        }
    
    def action_save_and_return(self):
        """
        Guarda los cambios y regresa a la vista de detalle.
        """
        self.ensure_one()
    
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detalles del Cliente'),
            'res_model': 'clientes.cliente',
            'view_mode': 'form',
            'views': [(self.env.ref('clientes.view_clientes_form').id, 'form')],
            'target': 'current',
            'res_id': self.id,
        }
    
    def action_match_persona_by_rfc(self):
        self.ensure_one()
        r = (self.rfc or '').strip().upper()
        if not r:
            raise UserError(_("Captura el RFC para buscar."))

        Person = self.env['persona.persona'].sudo()
        p = Person.search([('rfc', '=', r)], limit=2)
        if len(p) > 1:
            raise UserError(_("Hay más de una persona con el RFC %s.") % r)
        if not p:
            raise UserError(_("No existe una persona con el RFC %s.") % r)

        existing = self.env['clientes.cliente'].sudo().search([('persona_id', '=', p.id)], limit=1)
        if existing:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Cliente existente'),
                'res_model': 'clientes.cliente',
                'view_mode': 'form',
                'res_id': existing.id,
                'target': 'current',
            }
        self.persona_id = p.id
        return


        # No existe: solo enlaza la persona para autorrellenar los related
        self.persona_id = p.id
        return
