from odoo import models, fields

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

    _sql_constraints = [
        ("sucursal_codigo_uniq", "unique(codigo)", "El código de la sucursal debe ser único."),
    ]
