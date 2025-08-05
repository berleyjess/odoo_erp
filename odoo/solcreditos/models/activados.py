# solcreditos/models/solcredito_autorizacion_ext.py
from odoo import models, fields, api

class activados(models.Model):
    _name = 'solcreditos.activacion'
    #_inherit = 'solcreditoautorizaciones.autorizacion'  # Hereda del modelo de autorizaciones

    status = fields.Selection(string = "Dictamen", selection=[
        ('1', 'Aprobado'),
        ('0', 'Rechazado')
    ], required = True, default = '0')

    descripcion = fields.Char(
        string='Descripción',
        help='Descripción del status actual. Puede ser un texto breve que explique el estado del activo.', required=True
    )

    fecha = fields.Date(
        string='Fecha',
        help='Fecha en la que se registró el estado del status.',
        default=fields.Date.context_today, readonly=True

    )

    activacion_id = fields.Many2one(
        'solcreditos.solcredito',
        string='Activación',
        ondelete='cascade'
    )