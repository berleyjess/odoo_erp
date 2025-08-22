from odoo import models, fields, api

class cargos_ext(models.Model):
    _inherit = 'cargosdetail.cargodetail'

    contrato_id = fields.Many2one('contratos.contrato', string = "Contrato")