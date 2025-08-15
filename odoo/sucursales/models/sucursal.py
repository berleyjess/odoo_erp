from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re

class Sucursal(models.Model):
    _name = "sucursales.sucursal"
    _description = "Sucursal"
    _rec_name = "nombre"
    _order = "nombre"

    nombre = fields.Char(string="Nombre", required=True, size=50)
    name = fields.Char(related="nombre", store=True, readonly=True, index=True)

    codigo = fields.Char(
        string="Código", required=True, readonly=True, copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("seq_sucursal_code") or "/",
    )
    empresa = fields.Many2one('empresas.empresa', string="Empresa", ondelete='restrict', index=True)

    calle = fields.Char("Calle")
    numero = fields.Char("Número")
    localidad = fields.Many2one("localidades.localidad", string="Ciudad/Localidad")
    cp = fields.Char("Código Postal", size=5)
    activa = fields.Boolean(string="Activa", default=True, required=True)

    serie = fields.Char(string='Serie', required=True, size=2, index=True)

    _sql_constraints = [
        ("sucursal_codigo_uniq", "unique(codigo)", "El código de la sucursal debe ser único."),
        # Unicidad global de la serie (tras normalizar a MAYÚSCULAS)
        ("sucursal_serie_uniq", "unique(serie)", "La serie ya está en uso por otra sucursal."),
    ]

    # --- Normalización a MAYÚSCULAS y sin espacios ---
    @api.model
    def create(self, vals):
        serie = vals.get('serie')
        if serie:
            vals['serie'] = serie.strip().upper()
        return super().create(vals)

    def write(self, vals):
        serie = vals.get('serie')
        if serie:
            vals['serie'] = serie.strip().upper()
        return super().write(vals)

    # --- Validación: exactamente 2 letras ---
    @api.constrains('serie')
    def _check_serie(self):
        regex = re.compile(r'^[A-Z]{2}$')  # exactamente 2 letras A-Z
        for rec in self:
            if rec.serie and not regex.match(rec.serie):
                raise ValidationError("La serie debe tener exactamente 2 letras (A–Z).")
