# empresas/models/empresa.py
from odoo import fields, models, api

class empresa(models.Model):
    _name = 'empresas.empresa'
    _description = "Modelo de Empresa, almacena el catálogo de empresas."
    _rec_name = 'nombre'

    nombre = fields.Char(string="Nombre", required=True, size=50)
    descripcion = fields.Char(string="Descripción", size=50)
    telefono = fields.Char(string="Teléfono", size=10)
    razonsocial = fields.Char(string="Razón Social", required=True)
    rfc = fields.Char(string="RFC", required=True, size=14)
    cp = fields.Char(string="Código Postal", required=True, size=5)
    calle = fields.Char(string="Calle", size=20)
    numero = fields.Char(string="Número", size=32)

    # (opcional conservar)
    usuario_id = fields.Many2one('res.users', string='Usuario', required=True, ondelete='restrict', index=True,
                                 default=lambda self: self.env.user.id)

    codigo = fields.Char(
        string='Código', size=10, required=True, readonly=True, copy=False,
        default=lambda self: self._generate_code(),
    )


    @api.model
    def create(self, vals):
        for k in ('nombre', 'razonsocial', 'rfc'):
            if k in vals and vals[k]:
                vals[k] = vals[k].upper()
        return super().create(vals)

    def write(self, vals):
        for k in ('nombre', 'razonsocial', 'rfc'):
            if k in vals and vals[k]:
                vals[k] = vals[k].upper()
        return super().write(vals)

    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_emp_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(2)}"
