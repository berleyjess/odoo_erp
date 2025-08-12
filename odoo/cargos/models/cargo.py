from odoo import models, fields

class cargo(models.Model):
    _name = 'cargos.cargo'

    #importe = fields.Float(string = "Importe", required = True, store = True)
    concepto = fields.Char(string = "Concepto", required = True, store = True)
    periodicidad = fields.Selection(string = "Periodicidad", selection =[
        ('0', "Única"),
        ('1', "Diaria"),
        ('2', "Mensual")
    ]
    , required = True, store = True)

    tipo = fields.Selection(string = "Vínculo", selection = [
        ('0', "Superficie"),
        ('1', "Monto"),
        ('2', "Contrato")
    ],
    required = True, store = True)
    producto_id = fields.Many2one('productos.producto', string = "Producto", required = True, store = True)

    facturable = fields.Boolean(string = "Facturable", required = True, store = True, default = False)