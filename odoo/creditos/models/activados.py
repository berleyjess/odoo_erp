# creditos/models/credito_autorizacion_ext.py
from odoo import models, fields, api

class activados(models.Model):
    _name = 'creditos.activacion'
    #_inherit = 'creditoautorizaciones.autorizacion'  # Hereda del modelo de autorizaciones

    status = fields.Selection(string = "Dictamen", selection=[
        ('1', 'Habilitar'),
        ('0', 'Deshabilitar')
    ], required = True, default = '1')

    descripcion = fields.Char(
        string='Descripción', required=True
    )

    fecha = fields.Date(
        string='Fecha',
        help='Fecha en la que se registró el estado del status.',
        default=fields.Date.context_today, readonly=True

    )

    credito_id = fields.Many2one(
        'creditos.credito',
        string='Activación',
        ondelete='cascade'
    )