# sucursales/models/sucursal.py
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
    empresa = fields.Many2one('empresas.empresa', string="Empresa", required=True, ondelete='restrict', index=True)

    # (Puedes mantener usuario_id si quieres registrar “quién la creó”)
    usuario_id = fields.Many2one('res.users', string='Usuario', required=True, ondelete='restrict', index=True,
                                 default=lambda self: self.env.user.id)

    calle = fields.Char("Calle")
    numero = fields.Char("Número")
    localidad = fields.Many2one("localidades.localidad", string="Ciudad/Localidad")
    cp = fields.Char("Código Postal", size=5)
    activa = fields.Boolean(string="Activa", default=True, required=True)

    serie = fields.Char(string='Serie', required=True, size=2, index=True)

    tiposucursal = fields.Selection(
        selection=[("0", "Insumos"), ("1", "Granos"), ("2", "Ferretería")],
        string="Categoría del Producto",
        required=True,
        default='0'
    )

    _sql_constraints = [
        ("sucursal_codigo_uniq", "unique(codigo)", "El código de la sucursal debe ser único."),
        ("sucursal_serie_uniq", "unique(serie)", "La serie ya está en uso por otra sucursal."),
    ]

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

    @api.constrains('serie')
    def _check_serie(self):
        regex = re.compile(r'^[A-Z]{2}$')
        for rec in self:
            if rec.serie and not regex.match(rec.serie):
                raise ValidationError("La serie debe tener exactamente 2 letras (A–Z).")
