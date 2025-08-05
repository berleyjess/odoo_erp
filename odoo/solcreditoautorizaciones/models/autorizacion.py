# autorizaciones/models/autorizacion.py
from odoo import models, fields, api, _


class cliente(models.Model):
    _name='solcreditoautorizaciones.autorizacion'  #Modelo.Autorizacion ("nombre del modulo"."nombre del modelo")
    _description='Estatus de activos'
    #_rec_name='nombre'  #Nombre del campo que se mostrará en las vistas de lista y búsqueda
    
    """status = fields.Selection(
        selection=[
            ('0', 'Desabilitado'),
            ('1', 'Habilitado')
        ],
        string='Estatus',
        default='0',
        required=True
    )"""

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

    """referenciaSolCredito = fields.Many2one(
        'solcreditos.solcredito',
        string='Referencia a Solicitud de Crédito',
        help='Referencia a la solicitud de crédito asociada a este activo.'
    )"""


