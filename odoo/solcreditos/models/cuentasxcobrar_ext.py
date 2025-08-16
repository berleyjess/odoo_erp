# solcreditos/models/cuentasxcobrar_ext.py
from odoo import fields, models

class CxCContrato(models.Model):
    _inherit = 'cuentasxcobrar.cuentaxcobrar'
    #_name = 'solcredito.cuentaxcobrar_ext'

    contrato_id = fields.Many2one(
        'solcreditos.solcredito',
        string="Solicitud/Contrato",
        index=True,
        ondelete='cascade'
    )

    