# proveedores/models/proveedor.py
# Modelo “rol Proveedor” sobre persona.persona (delegación via _inherits).
# Define código propio, contactos y políticas: no sobrescribir datos de Persona;
# sólo rellenar huecos, validar duplicados (incluye archivados).

import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.exceptions import ValidationError, UserError, RedirectWarning

# RFCs genéricos SAT (si los usas para crear persona mínima).  ← (ver “Depurar” abajo)
RFC_GENERICS = ('XAXX010101000', 'XEXX010101000')

class Proveedor(models.Model):
    """Rol Proveedor: delega identidad/dirección hacia persona.persona con _inherits.

    Campos related apuntan a persona_id.* (no se guardan aquí); la escritura se
    controlará en write() para sólo completar vacíos en Persona, nunca sobrescribir.
    """
    _name = 'proveedores.proveedor'
    _description = 'Proveedor'
    _rec_name = 'nombre'
    _order = 'codigo'
    _inherits = {'persona.persona': 'persona_id'}

    # Clave de delegación (_inherits): el registro de persona donde viven los datos.
    persona_id = fields.Many2one(
        'persona.persona', string="Persona", required=True, ondelete='restrict', index=True
    )

    # Código interno del proveedor (secuencia propia)
    codigo = fields.Char(
        string='Código',
        size=10,
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_code(),
        help="Código interno autogenerado (ej. 000001). Controlado por la secuencia 'seq_prov_code'."
    )

    # ------ CAMPOS RELATED (se almacenan en persona) ------
    # Relateds a persona.* (proxy en la vista). NO se guardan aquí (store=False).
# La edición real se gobierna en write(): completar vacíos en persona, sin sobrescribir.

    nombre   = fields.Char(string="Razón social / Nombre", related='persona_id.name',      readonly=False, store=False)
    rfc      = fields.Char(string="RFC",                 related='persona_id.rfc',       readonly=False, store=False, index=True)
    email    = fields.Char(string="Email",               related='persona_id.email',     readonly=False, store=False)
    telefono = fields.Char(string="Teléfono",            related='persona_id.telefono',  readonly=False, store=False)

    codigop     = fields.Char(string="Código Postal",    related='persona_id.codigop',        readonly=False, store=False, size=5)
    localidad   = fields.Many2one('localidades.localidad', string="Ciudad/Localidad",        related='persona_id.localidad_id', readonly=False, store=False)
    colonia     = fields.Char(string="Colonia",          related='persona_id.colonia',        readonly=False, store=False)
    calle       = fields.Char(string="Calle",            related='persona_id.calle',          readonly=False, store=False)
    numero      = fields.Char(string="Número",           related='persona_id.numero_casa',    readonly=False, store=False)

    # ------ CAMPOS ADICIONALES (exclusivos del rol proveedor) ------
    descripcion = fields.Char(string="Descripción")

    # Contactos (heredan de contactos.contacto con M2O a proveedor)
    contacto = fields.One2many('contactos.contacto', 'proveedor_id', string="Contactos")

# Unicidad de código y de persona→proveedor (no puede haber dos proveedores para la misma persona).
# (SQL constraints: ver referencia de ORM).  ← deja el enlace en tu doc interna
    _sql_constraints = [
        ('proveedor_codigo_unique', 'unique(codigo)', 'El código de proveedor debe ser único.'),
        ('proveedor_persona_unique','unique(persona_id)', 'Esta persona ya está registrada como proveedor.'),
    ]

    # ===== Helpers =====
    # Helper: toma siguiente valor de 'seq_prov_code' y lo formatea a 6 dígitos.
    def _generate_code(self):
        seq = self.env['ir.sequence'].next_by_code('seq_prov_code') or '/'
        return (seq.split('/')[-1]).zfill(6)

    # ===== Onchange =====
    # Onchange: si el RFC existe en Persona y NO hay proveedor, autovincula persona.
# Si ya hay proveedor, muestra warning y NO enlaza (evita duplicados desde la vista).
    @api.onchange('rfc')
    def _onchange_rfc_autofill(self):
        """Si escriben un RFC y existe Persona: enlaza persona (si no hay proveedor ya).
           Si la persona ya es proveedor, muestra warning (no enlaza)."""
        r = (self.rfc or '').strip().upper()
        if not r or self.persona_id:
            return
        Person = self.env['persona.persona'].sudo()
        p = Person.search([('rfc', '=', r)], limit=1)
        if not p:
            return
        if self.env['proveedores.proveedor'].sudo().search_count([('persona_id', '=', p.id)]):
            return {
                'warning': {
                    'title': _('RFC ya registrado'),
                    'message': _('Ya existe un proveedor con este RFC. Usa "Buscar persona por RFC" para abrirlo.')
                }
            }
        self.persona_id = p.id

    # ===== Create/Write =====
    # CREATE: 1) Resolver/crear persona (por RFC),
#         2) Validar que esa persona no sea ya proveedor (incluye archivados),
#         3) Completar sólo campos vacíos en persona,
#         4) Limpiar relateds de vals,
#         5) Asegurar código y crear.

    @api.model
    def create(self, vals):
        Person = self.env['persona.persona'].sudo()

        # Normaliza RFC y resuelve persona si vino RFC
        r = (vals.get('rfc') or '').strip().upper()
        if not vals.get('persona_id') and r:
            p = Person.search([('rfc', '=', r)], limit=1)
            if p:
                vals['persona_id'] = p.id
            else:
            # crea persona mínima
                vals['persona_id'] = Person.create({
                    'name': vals.get('nombre') or _('SIN NOMBRE'),
                    'rfc': r or 'XAXX010101000',
                    'email': (vals.get('email') or '').strip().lower() or False,
                    'telefono': vals.get('telefono') or False,
                    'localidad_id': vals.get('localidad') or False,
                    'colonia': vals.get('colonia') or False,
                    'numero_casa': vals.get('numero') or False,
                    'calle': vals.get('calle') or False,
                    'codigop': vals.get('codigop') or False,
                }).id

        pid = vals.get('persona_id')

        # --- Validación fuerte: NO duplicar proveedor para una persona (activo o archivado)
        if pid and self.with_context(active_test=False).search_count([('persona_id', '=', pid)]):
            raise ValidationError(_("Esta persona ya está registrada como proveedor (validado por RFC/persona)."))

    # --- Llenar SOLO huecos en persona (nunca sobrescribir)
        if pid:
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

# SIEMPRE limpia relateds antes de crear
            for f in ('nombre','rfc','email','telefono','codigop','localidad','colonia','calle','numero'):
                vals.pop(f, None)

            # y luego asignas el código robusto y haces super().create(vals)
            if not vals.get('codigo'):
                vals['codigo'] = self._generate_code()

        return super().create(vals)

# WRITE: política de “no sobre-escritura”.
# Si el usuario intenta editar relateds y persona ya tiene valor, se bloquea;
# si están vacíos, se rellenan en persona. Luego se limpian de vals antes del super().
    def write(self, vals):
        vals = vals.copy()

    # Solo rellenar huecos en persona; bloquear sobrescritura
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
        attempted = {k: v for k, v in vals.items() if k in fill_map and v not in (None, False, '', [])}
        blocked_any = []

        for rec in self:
            p = rec.persona_id.sudo()
            updates = {}
            for k, v in attempted.items():
                tgt = fill_map[k]
                current = p[tgt]
                if not current:
                    updates[tgt] = (v.strip().lower() if k == 'email' and isinstance(v, str) else v)
                else:
                    blocked_any.append(k)
            if updates:
                p.write(updates)

    # Evitar que el write de Proveedor empuje a persona via related
        for k in attempted.keys():
            vals.pop(k, None)

        if blocked_any:
            ctx = {'active_id': self[:1].persona_id.id}  # usa el primero si viene un conjunto
            raise RedirectWarning(
                _(
                    "No puedes editar desde Proveedor los campos ya definidos en Personas: %s. "
                    "Rellena aquí solo los vacíos; para cambiar un valor existente, edítalo en Personas."
                ) % ", ".join(sorted(set(blocked_any))),
                self.env.ref('proveedores.action_open_persona_modal_from_warning').id,
                _("Editar en Personas"),
                additional_context=ctx,
            )
        return super().write(vals)
