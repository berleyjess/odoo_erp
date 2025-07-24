from odoo import models, fields, api

class bodega(models.Model):
    _name = 'bodega'

    empresa = fields.Many2one('empresa', string = "Empresa", ondelete='cascade')
    sucursal = fields.Many2one('sucursal', string = "Sucursal", required = True)
    nombre = fields.Char(string = "Nombre", required = True, size = 20)
    activa = fields.Boolean(string="Activa", required = True, default = True)
    codigo = fields.Char(
        string='Código',
        size=10,
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_code(),
        #help="Código único autogenerado con formato COD-000001"
    )

    def _generate_code(self):
        sequence = self.env['ir.sequence'].next_by_code('seq_bod_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(2)}"