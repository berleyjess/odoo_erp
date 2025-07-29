from odoo import models,fields

class predio_ext(models.Model):
    _name = 'solcreditos.predio_ext'
    _description = 'Extensión de Predios para solicitudes de créditos'
    _inherit = 'predios.predio'

    solcredito_id = fields.Many2one('solcreditos.solcredito', string="Solicitud de Crédito",
                                    ondelete='cascade')