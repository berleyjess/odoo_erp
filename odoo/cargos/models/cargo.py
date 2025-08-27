from odoo import models, fields, api

class cargo(models.Model):
    _name = 'cargos.cargo'
    _rec_name = 'concepto'

    concepto = fields.Char(string = "Concepto", required = True, store = True)
    descripcion = fields.Char(string = "Descripción del concepto", required = True)

    tipo = fields.Selection(string = "Tipo de Cargo", selection = [
        ('0', "Costo x Superficie"),
        ('1', "Porcentaje x Saldo Ejercido"),
        ('2', "Monto Único")
    ],
    required = True, store = True)

    producto_id = fields.Many2one('productos.producto', string = "Servicio Relacionado", required = True, store = True)

    facturable = fields.Boolean(string = "Facturable", required = True, store = True, default = False)

    iva = fields.Float(string = "Iva %", store = True, compute = '_calc_impuestos')
    ieps = fields.Float(string = "Ieps %", store = True, compute = '_calc_impuestos')

    @api.depends('producto_id')
    def _calc_impuestos(self):
        for i in self:
            i.iva = i.producto_id.iva
            i.ieps = i.producto_id.ieps

    @api.model
    def create(self, vals):
        # Convertir a mayúsculas antes de crear
        if 'concepto' in vals:
            vals['concepto'] = vals['concepto'].upper() if vals['concepto'] else False
        return super().create(vals)

    def write(self, vals):
        # Convertir a mayúsculas antes de actualizar
        if 'concepto' in vals:
            vals['concepto'] = vals['concepto'].upper() if vals['concepto'] else False
        return super().write(vals)