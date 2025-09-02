# -*- coding: utf-8 -*-
"""
    Modelo 'clientes.cliente': rol "Cliente" DELEGA en persona.persona vía _inherits.
Regla clave: los datos de identidad/dirección viven en Personas; aquí solo se ven como related.
"""
"""Cartera de clientes (_name='clientes.cliente').
- Delegación: _inherits = {'persona.persona': 'persona_id'} (identidad/contacto viven en Personas). :contentReference[oaicite:3]{index=3}
- Código interno autogenerado por ir.sequence 'seq_client_code'. :contentReference[oaicite:4]{index=4}
- Related fields a persona (store=False) para no duplicar datos. :contentReference[oaicite:5]{index=5}
- Reglas: no permitir 2 clientes para la misma persona (SQL + validación Python). :contentReference[oaicite:6]{index=6}
"""

import re
from odoo.exceptions import ValidationError
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from odoo.exceptions import UserError, ValidationError, RedirectWarning
# _logger se usa para depuración; si no lo usas, elimina import logging y la variable.
_logger = logging.getLogger(__name__)

RFC_GENERICS = ('XAXX010101000', 'XEXX010101000')

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
    # _inherits (delegación): cada cliente apunta a una persona mediante persona_id
    # y expone sus campos como si fueran propios. :contentReference[oaicite:1]{index=1}
    _inherits = {'persona.persona': 'persona_id'}
    _order = 'codigo'  #Orden por defecto en las vistas de lista
    
    # Código interno: se llena en create() usando ir.sequence 'seq_client_code'. :contentReference[oaicite:8]{index=8}
    codigo = fields.Char( #Código interno del Cliente
        string='Código',
        size=10,
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_code(),
        help="Código interno autogenerado (ej. 000001). Controlado por la secuencia 'seq_client_code'."
    )

# Enlace de delegación (_inherits): Cliente -> Persona. ondelete='restrict' para no dejar huérfanos. :contentReference[oaicite:7]{index=7}
    persona_id = fields.Many2one('persona.persona', required=True, ondelete='restrict', index=True, string="Persona")
    # Campos related: proxy a subcampos de persona; aquí no se almacenan (store=False). :contentReference[oaicite:2]{index=2}
    nombre = fields.Char(string="Nombre/Razón social", readonly=False, required=True,related='persona_id.name',store=False,help="Nombre completo o razón social del cliente.")
    rfc = fields.Char(string="RFC",size=13, readonly=False, required=False,related='persona_id.rfc',store=False, index=True, help="Registro Federal de Contribuyentes")

    #es_cliente = fields.Boolean(default=True, related='persona_id.es_cliente')

    # Constantes de validación de RFC
    
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
    # RFC genéricos SAT admitidos para altas mínimas; NO pasan validación estricta.
    RFC_GENERICOS = ('XAXX010101000', 'XEXX010101000')


# Devuelve el contacto marcado como 'principal' (o el primero si no hay principal).
    def _get_contacto_ppal(self):
        self.ensure_one()
        # Preferir el marcado como principal; si no hay, toma el primero
        return self.contacto.filtered(lambda c: c.es_principal)[:1] or self.contacto[:1]

# Si teléfono/email en Persona están vacíos, los rellena con el contacto principal (no sobrescribe).
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



    # Régimen fiscal con dominio dinámico por 'tipo' (ver _onchange_tipo).
    regimen = fields.Many2one('clientes.c_regimenfiscal',
                              string = "Régimen Fiscal",
                              domain="[('tipo', 'in', [tipo == '0' and '0' or '1', '2'])]",
                              help="Régimen fiscal del cliente. El dominio se recalcula dinámicamente en _onchange_tipo."
    )

    codigop = fields.Char(string="Código Postal", size=5, readonly=False,related='persona_id.codigop',store=False)
    localidad = fields.Many2one('localidades.localidad', readonly=False,related='persona_id.localidad_id',store=False, string = "Ciudad/Localidad")
    calle = fields.Char(string = "Calle", size = 32, readonly=False,related='persona_id.calle', store=False) 
    colonia      = fields.Char(string="Colonia", readonly=False,related='persona_id.colonia', store=False)
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

    usar_rfc_generico = fields.Boolean(
        string="Usar RFC genérico (XAXX010101000)",
        default=False,
        help="Marca esto SOLO si quieres registrar al cliente con RFC genérico."
    )
    
    #Referencias Laborales
    empresa = fields.Char(string = "Empresa donde labora", store = True, size = 32)
    puesto = fields.Char(string = "Puesto que desempeña", store = True)
    ingresomensual = fields.Float(string = "Ingreso Mensual Estimado", store = True, default = 0.0)

    #Relación con contactos
# Contactos del cliente (externos). Se usa para auto-rellenar tel/email si Persona está vacía.
    contacto = fields.One2many('contactos.contacto', 'cliente_id', string="Contactos", help="Contactos externos relacionados con este cliente.")


    # ONCHAGE METHODS

    """
        Actualiza el dominio del campo 'regimen' dependiendo del tipo de cliente.
        Además, muestra una advertencia si hay RFC capturado para que se valide
        coherencia con el tipo seleccionado.

        Retorna:
            dict: dominio dinámico para el campo 'regimen' y un warning opcional.
    """
# Invariantes a nivel BD:
# - codigo único
# - una persona no puede ser cliente dos veces (persona_id único) :contentReference[oaicite:10]{index=10}
    _sql_constraints = [
    ('cliente_codigo_unique', 'unique(codigo)', 'El código de cliente debe ser único.'),
    ('cliente_persona_unique','unique(persona_id)', 'Esta persona ya está registrada como cliente.'),
    ]

    
    # -----------------------------
    # Onchange: auto-rellenar por RFC
    # -----------------------------

    # Al teclear RFC: si existe Persona sin Cliente, enlaza persona_id;
    # si ya es Cliente, muestra warning (no enlaza). (onchange solo en formularios nuevos). 
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

    # -----------------------------
  
    # Logica de negocio / hooks.

# Helper: obtiene el siguiente consecutivo de 'seq_client_code' y lo formatea a 6 dígitos. :contentReference[oaicite:11]{index=11}
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
    

    # Flujo de alta de Cliente:
# 1) Resolver/crear persona_id (por RFC si lo hay; si no, persona mínima con RFC genérico).
# 2) Evitar duplicados (mira activos e inactivos con active_test=False). :contentReference[oaicite:12]{index=12}
# 3) Rellenar SOLO huecos en persona (nunca pisar valores existentes).
# 4) Limpiar vals de relateds para que no intente escribirlos en Cliente.
# 5) Asignar código con ir.sequence si no viene. :contentReference[oaicite:13]{index=13}
# 6) Sincronizar tel/email desde contacto principal si persona carece de ellos.
    @api.model
    def create(self, vals):
        Person = self.env['persona.persona'].sudo()
        r = (vals.get('rfc') or '').strip().upper()

        # 1) Asegurar persona_id
        if not vals.get('persona_id'):
            if r:
                p = Person.search([('rfc', '=', r)], limit=1)
                if p:
                    vals['persona_id'] = p.id
                else:
                    vals['persona_id'] = Person.create({
                        'name': vals.get('nombre') or _('SIN NOMBRE'),
                        'rfc': r,
                        'email': (vals.get('email') or '').strip().lower() or False,
                        'telefono': vals.get('telefono') or False,
                        'localidad_id': vals.get('localidad') or False,
                        'colonia': vals.get('colonia') or False,
                        'numero_casa': vals.get('numero') or False,
                        'calle': vals.get('calle') or False,
                        'codigop': vals.get('codigop') or False,
                    }).id
            else:
                if vals.get('usar_rfc_generico'):
                    vals['persona_id'] = Person.create({
                        'name': vals.get('nombre') or _('SIN NOMBRE'),
                        'rfc': self.RFC_GENERICOS[0],  # XAXX010101000
                        'email': (vals.get('email') or '').strip().lower() or False,
                        'telefono': vals.get('telefono') or False,
                        'localidad_id': vals.get('localidad') or False,
                        'colonia': vals.get('colonia') or False,
                        'numero_casa': vals.get('numero') or False,
                        'calle': vals.get('calle') or False,
                        'codigop': vals.get('codigop') or False,
                    }).id
                else:
                    # Pide explícitamente el RFC o marcar el checkbox
                    raise ValidationError(_("RFC obligatorio para crear cliente. "
                                            "Usa 'Crear y editar…' y captura el RFC, "
                                            "o marca 'Usar RFC genérico' en el formulario."))
        pid = vals['persona_id']
    # 2) NO duplicar cliente para la misma persona (incluye archivados)
        if self.with_context(active_test=False).search_count([('persona_id', '=', pid)]):
            raise ValidationError(_("Esta persona ya está registrada como cliente (validado por RFC/persona)."))

    # 3) Rellenar SOLO huecos en persona (nunca sobrescribir valores existentes)
        p = Person.browse(pid)
        updates = {}
        if r and not p.rfc:
            updates['rfc'] = r
        if vals.get('nombre') and not p.name:
            updates['name'] = vals['nombre']
        if vals.get('email') and not p.email:
            updates['email'] = (vals['email'] or '').strip().lower()
        if vals.get('telefono') and not p.telefono:
            updates['telefono'] = vals['telefono']
        if vals.get('codigop') and not p.codigop:
            updates['codigop'] = vals['codigop']
        if vals.get('localidad') and not p.localidad_id:
            updates['localidad_id'] = vals['localidad']
        if vals.get('colonia') and not p.colonia:
            updates['colonia'] = vals['colonia']
        if vals.get('calle') and not p.calle:
            updates['calle'] = vals['calle']
        if vals.get('numero') and not p.numero_casa:
            updates['numero_casa'] = vals['numero']
        if updates:
            p.write(updates)

    # 4) Limpiar vals para que Cliente no intente escribir en campos related
        for f in ('nombre', 'rfc', 'email', 'telefono', 'codigop', 'localidad', 'colonia', 'calle', 'numero'):
            vals.pop(f, None)

    # 5) Generar código (obligatorio) si no vino
        if not vals.get('codigo'):
            vals['codigo'] = self._generate_code()

        rec = super().create(vals)
        rec._sync_persona_from_contact()
        return rec



    # Edición controlada:
# - Si el usuario intenta cambiar relateds y Persona YA los tiene, bloquear y pedir edición en Personas.
# - Si están vacíos en Persona, permitir rellenarlos desde Cliente (los escribe en persona). 
    def write(self, vals):
        vals = vals.copy()

    # Campos de Cliente que realmente pertenecen a persona.persona
        fill_map = {
            'nombre':   'name',
            'rfc':      'rfc',
            'email':    'email',
            'telefono': 'telefono',
            'codigop':  'codigop',
            'localidad':'localidad_id',
            'colonia':  'colonia',
            'calle':    'calle',
            'numero':   'numero_casa',
        }

    # Solo consideramos los que el usuario intenta editar
        attempted = {k: v for k, v in vals.items() if k in fill_map and v not in (None, False, '', [])}
        blocked_any = []

    # Por cada registro (write puede ser multi)
        for rec in self:
            p = rec.persona_id.sudo()
            updates = {}
            blocked = []

            for k, v in attempted.items():
                tgt = fill_map[k]
                current = p[tgt]
                if not current:
                    # normalizaciones mínimas
                    if k == 'email' and isinstance(v, str):
                        updates[tgt] = v.strip().lower() or False
                    else:
                        updates[tgt] = v
                else:
                    blocked.append(k)

            if blocked:
                blocked_any.extend(blocked)
            if updates:
                p.write(updates)

    # Limpiar para que Cliente no intente escribir los related
        for k in attempted.keys():
            vals.pop(k, None)

    # Si intentaron sobrescribir algo ya definido, error explícito
        if blocked_any:
            blocked_any = sorted(set(blocked_any))
            raise ValidationError(_(
                "No puedes editar desde Cliente los campos ya definidos en Personas: %s. "
                "Rellena aquí solo los vacíos; para cambiar un valor existente, edítalo en Personas."
            ) % ", ".join(blocked_any))

        return super().write(vals)

    # Redundante con _check_rfc (también verifica formato/unicidad).
    # Sugerencia: mantener una sola validación para evitar duplicados.
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

# Valida RFC obligatorio + longitud según tipo + formato SAT + unicidad entre clientes (salvo genéricos). :contentReference[oaicite:14]{index=14}
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

    @api.constrains('estado_civil', 'conyugue', 'regimenconyugal')
    def _check_requeridos_conyugue(self):
        for record in self:
            if record.estado_civil in ['casado', 'union_libre']:
                if not record.conyugue:
                    raise ValidationError("¡El nombre del cónyuge es obligatorio!")
                if not record.regimenconyugal:
                    raise ValidationError("¡El régimen conyugal es obligatorio!")
            
    # ======= Tus onchanges/constraints originales que NO choquen con persona =======
    
    # Ajusta dominio de 'regimen' según 'tipo' (PF/PM).
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


#-----------------------------------

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

# Acciones para navegación entre vistas (list/form/modal). Window actions: ir.actions.act_window. :contentReference[oaicite:16]{index=16}

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
    
    #----------------------
    
    def action_match_persona_by_rfc(self):
        self.ensure_one()
        r = (self.rfc or '').strip().upper()
        if not r:
            raise UserError(_("Captura el RFC para buscar."))

        Person = self.env['persona.persona'].sudo()
        p = Person.search([('rfc', '=', r)], limit=1)
        if not p:
            raise UserError(_("No existe una Persona con el RFC %s.") % r)

        # ¿Hay un cliente (activo o inactivo) ligado a esa persona?
        Cliente = self.env['clientes.cliente'].with_context(active_test=False)
        existing = Cliente.search([('persona_id', '=', p.id)], limit=1)
        if existing:
            # Si estaba inactivo, lo reactivamos aquí y lo abrimos
            if not existing.active:
                existing.sudo().write({'active': True})
            return {
                'type': 'ir.actions.act_window',
                'name': _('Cliente'),
                'res_model': 'clientes.cliente',
                'view_mode': 'form',
                'res_id': existing.id,
                'target': 'current',
            }

        # No hay cliente aún → preligamos persona y seguimos creando
        self.persona_id = p.id
        return
