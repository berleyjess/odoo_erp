# personas/models/persona.py
# Personas: modelo base sin roles.
# Guarda identidad, contacto y ubicación. Válida RFC/Email/Teléfono y
# normaliza mayúsculas/minúsculas en create/write.
"""Modelo base 'persona.persona'.
- No maneja roles (cliente/proveedor) ni lógica cruzada.
- Exponer campos mínimos reutilizables por otros módulos vía _inherits/_inherit.
- 'name' es el rec_name mostrado en listas/búsquedas.
"""

import re
from datetime import date as pydate
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

# --- Constantes de validación/normalización ---
# PHONE_DIGITS: regex para extraer solo dígitos de teléfonos.
# GENERIC_RFC: RFC genérico permitido por SAT (no se fuerza unicidad).
# RFC_RE: patrón general (moral/física) para validar estructura y fecha YYMMDD.
# EMAIL_RE: formato básico de emails.
PHONE_DIGITS = re.compile(r'\D')
GENERIC_RFC = 'XAXX010101000'   # RFC genérico SAT

RFC_RE = re.compile(r'^([A-ZÑ&]{3,4})(\d{2})(\d{2})(\d{2})([A-Z0-9]{3})$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

class Persona(models.Model):
    _name = 'persona.persona'
    _description = 'Persona base'
    _rec_name = 'name'

    # Identidad básica
    name = fields.Char(string="Nombre", required=True)
    fecha_nacimiento = fields.Date(string="Fecha de nacimiento", compute="_compute_fecha_nac_from_rfc", store=True)

    # Contacto
    telefono = fields.Char(string="Teléfono")
    email = fields.Char(string="Email")

    # Ubicación
    localidad_id = fields.Many2one('localidades.localidad', string="Localidad")
    colonia = fields.Char(string="Colonia")
    numero_casa = fields.Char(string="Número de casa")
    calle = fields.Char(string="Calle")
    codigop = fields.Char(string="Codigo Postal", size=5)

    # Identificador fiscal
    rfc = fields.Char(string="RFC", index=True)

    # (Opcional) Archivado
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('persona_tel_norm_unique', 'unique(telefono_idx)',
        'Este teléfono ya está registrado en otra persona.'),
    ]

    telefono_idx = fields.Char(
        string="Tel (índice)",
        compute="_compute_tel_idx",
        store=True,
        index=True,
        help="Teléfono solo con dígitos, para búsquedas/índices."
    )

    @api.depends('telefono')
    def _compute_tel_idx(self):
        for r in self:
            digits = re.sub(PHONE_DIGITS, '', r.telefono or '')
            r.telefono_idx = digits[-10:] if digits else False
    # -------------------------
    # Normalizaciones guardado
    # -------------------------

    # Normalización al guardar:
# - RFC -> mayúsculas; Email -> minúsculas; Teléfono -> trim.
# Se realiza tanto en create como en write para mantener consistencia.

    @api.model
    def create(self, vals):
        if vals.get('rfc'):
            vals['rfc'] = vals['rfc'].strip().upper()
        if vals.get('email'):
            vals['email'] = vals['email'].strip().lower()
        if vals.get('telefono'):
            vals['telefono'] = vals['telefono'].strip()
        return super().create(vals)

    def write(self, vals):
        if 'rfc' in vals and vals['rfc']:
            vals['rfc'] = vals['rfc'].strip().upper()
        if 'email' in vals and vals['email']:
            vals['email'] = vals['email'].strip().lower()
        if 'telefono' in vals and vals['telefono']:
            vals['telefono'] = vals['telefono'].strip()
        return super().write(vals)

    # -------------------------
    # Validaciones
    # -------------------------

# Valida variantes aceptadas en MX:
# 10 dígitos, +52 + 10, y prefijo legacy 521 (WhatsApp). Rechaza otros formatos.
    @api.constrains('telefono')
    def _check_telefono_mx(self):
        """
        Acepta:
          - 10 dígitos nacionales (XXXXXXXXXX)
          - Formato internacional MX: +52XXXXXXXXXX
          - Con separadores (espacios, guiones, paréntesis)
          - También tolera el prefijo histórico '521' de WhatsApp
        """
        for rec in self:
            if not rec.telefono:
                continue
            digits = re.sub(r'\D', '', rec.telefono)
            ok = (
                len(digits) == 10 or                              # nacional
                (len(digits) == 12 and digits.startswith('52')) or# +52 + 10
                (len(digits) == 13 and digits.startswith('521'))  # +521 + 10 (tolerado)
            )
            if not ok:
                raise ValidationError(_(
                    "Teléfono inválido. Usa 10 dígitos (nacional) o +52 seguido de 10 dígitos."
                ))

# Enforce unicidad de RFC solo si NO es el genérico SAT (GENERIC_RFC).
# (Se usa constraint Python en lugar de SQL para permitir repetición del genérico). :contentReference[oaicite:3]{index=3}
    @api.constrains('rfc')
    def _check_rfc_unico_no_generico(self):
        """Unicidad de RFC solo si NO es el genérico del SAT."""
        for rec in self:
            if rec.rfc and rec.rfc != GENERIC_RFC:
                dup = rec.search_count([('rfc', '=', rec.rfc), ('id', '!=', rec.id)])
                if dup:
                    raise ValidationError(_("Ya existe una persona con este RFC."))

# Valida formato básico de email (regex simple).
    @api.constrains('email')
    def _check_email_format(self):
        for rec in self:
            if rec.email and not EMAIL_RE.match(rec.email):
                raise ValidationError(_("Email inválido: verifique el formato."))

# Valida estructura del RFC (12/13) y que YYMMDD represente una fecha válida
# en siglo 19xx o 20xx. Lanza error si la fecha es inválida.
    @api.constrains('rfc')
    def _check_rfc_sat(self):
        """
        Valida RFC según patrón SAT:
          - Personas morales: 3 letras + YYMMDD + 3 alfanum (12)
          - Personas físicas: 4 letras + YYMMDD + 3 alfanum (13)
        Además, valida que la fecha YYMMDD sea calendario válido (acepta siglo 19xx o 20xx).
        """
        for rec in self:
            if not rec.rfc:
                continue
            rfc = rec.rfc.strip().upper()
            m = RFC_RE.match(rfc)
            if not m:
                raise ValidationError(_("RFC inválido. Formato esperado del SAT (12 o 13 caracteres)."))
            yy, mm, dd = int(m.group(2)), int(m.group(3)), int(m.group(4))
            valid_date = False
            # Acepta 19xx y 20xx
            for century in (1900, 2000):
                try:
                    pydate(century + yy, mm, dd)
                    valid_date = True
                    break
                except ValueError:
                    continue
            if not valid_date:
                raise ValidationError(_("RFC inválido: fecha YYMMDD no válida en el RFC."))

    # -------------------------
    # Cálculos automáticos
# Calcula fecha de nacimiento solo para personas físicas (RFC 13).
# Usa fields.Date.context_today() para decidir el siglo (2000/1900) de forma TZ-safe. :contentReference[oaicite:4]{index=4}
    @api.depends('rfc')
    def _compute_fecha_nac_from_rfc(self):
        """Extrae YYMMDD del RFC y calcula la fecha de nacimiento.
        Solo aplica a PERSONA FÍSICA (prefijo de 4 letras, RFC de 13)."""
        today = fields.Date.context_today(self)
        yy_now = today.year % 100  # dos dígitos del año actual
        for p in self:
            p.fecha_nacimiento = False
            r = (p.rfc or '').strip().upper()
            m = RFC_RE.match(r)
            if not m:
                continue
            pref = m.group(1)
            # Persona física: 4 letras al inicio (13 caracteres total)
            if len(pref) != 4 or len(r) != 13:
                # Para morales (3 letras) el YYMMDD es fecha de constitución; aquí la ignoramos.
                continue
            try:
                yy = int(m.group(2))
                mm = int(m.group(3))
                dd = int(m.group(4))
                century = 2000 if yy <= yy_now else 1900
                p.fecha_nacimiento = pydate(century + yy, mm, dd)
            except Exception:
                # Si MM/DD inválidos, deja vacío
                p.fecha_nacimiento = False