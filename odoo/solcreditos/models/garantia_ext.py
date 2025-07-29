#garantia_ext.py
from odoo import fields, models

class garantia_ext(models.Model):

    _name = 'solcreditos.garantia_ext'
    _description = 'Extensión del modelo de Garantías'
    _inherit = 'garantias.garantia'  # Hereda del modelo de garantías existente
    #garantia_id = fields.Many2one('garantias.garantia', string="Garantía", ondelete='cascade')
    solcredito_id = fields.Many2one('solcreditos.solcredito', string="Solicitud")
    #titularr = fields.Char(string="Titular de la garantía", required=True)