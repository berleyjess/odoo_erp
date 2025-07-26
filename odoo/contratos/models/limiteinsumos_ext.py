from odoo import models, fields

class limiteinsumo(models.Model):
    _name = 'contratos.limiteinsumo_ext'
    _description = 'Límite de insumos por contrato extendido'
    _inherit = 'limiteinsumos.limiteinsumo'

    contrato_id = fields.Many2one('contratos.contrato', string="Contrato", required=True, ondelete='cascade')

