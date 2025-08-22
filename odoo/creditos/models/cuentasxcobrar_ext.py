# creditos/models/cuentasxcobrar_ext.py
from odoo import fields, models

class CxCContrato(models.Model):
    _inherit = 'cuentasxcobrar.cuentaxcobrar'
    #_name = 'credito.cuentaxcobrar_ext'

    contrato_id = fields.Many2one(
        'creditos.credito',
        string="Solicitud/Contrato",
        index=True,
        ondelete='cascade'
    )

    