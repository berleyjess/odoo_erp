from odoo import models, fields

class asignacion(models.Model):
    _name = 'asignacion'
    _description = 'Asignacion de contratos a clientes'

    cliente = fields.Many2one('cliente', string="Nombre", required=True)
    contrato = fields.Many2one('contrato', string="Contrato", required=True)
    #superficie = fields.Float(string="Superficie Habilitada", required=True)
    aprobado = fields.Boolean(string = "Aprobado", default = False)
    bloqueado = fields.Boolean(string = "Bloqueado", default = False)
    activo = fields.Boolean(string = "Activo", default = False)

    predio = fields.One2many('predio.asignacion', 'asignacion_id', string = "Predios")
    
    cargosabono = fields.One2many('cargoabono.asignacion', 'cargoabono_id', string = "Estado de Cuenta")
