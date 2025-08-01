# autorizaciones/models/autorizacion.py
from odoo import models, fields, api, _


class cliente(models.Model):
    
    _name='autorizaciones.autorizacion'  #Modelo.Autorizacion ("nombre del modulo"."nombre del modelo")
    _description='Estatus de activos'
    _rec_name='nombre'  #Nombre del campo que se mostrará en las vistas de lista y búsqueda
    
    statusAutorizacion = fields.Selection(
        selection=[
            ('0', 'Desabilitado'),
            ('1', 'Habilitado')
        ],
        string='Estatus',
        default='0',
        required=True
    )

    descripcionAutorizacion = fields.Char(
        string='Descripción',
        help='Descripción del status actual. Puede ser un texto breve que explique el estado del activo.'
    )

    fechaAutorizacion = fields.Date(
        string='Fecha',
        help='Fecha en la que se registró el estado del status.'
    )

    referenciaSolCredito = fields.Many2one(
        'solcreditos.solcredito',
        string='Referencia a Solicitud de Crédito',
        help='Referencia a la solicitud de crédito asociada a este activo.'
    )


