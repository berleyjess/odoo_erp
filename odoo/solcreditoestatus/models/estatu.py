# solcreditoestatus/models/estatu.py
from odoo import models, fields, api, _


class SolCreditoEstatus(models.Model):
    
    _name='solcreditoestatus.solcreditoestatu' 
    _description='Estatus de solicitud de crédito'  #Descripción del modelo
    #_rec_name='status_display'  #Nombre del campo que se mostrará en las vistas de lista y búsqueda
    

    #status_display = fields.Char(
    #    string='Nombre del Estatus',
    #    compute='_compute_status_display',
    #    store=False
    #)

    #@api.depends('status')
    #def _compute_status_display(self):
    #    for record in self:
    #        record.status_display = dict(self._fields['status'].selection).get(record.status, '')

    status = fields.Selection(
        selection=[
            ('0', 'Desabilitado'),
            ('1', 'Habilitado')
        ],
        string='Estatus',
        default='0',
        required=True
    )

    descripcion = fields.Char(
        string='Descripción',
        help='Descripción del status actual. Puede ser un texto breve que explique el estado del activo.', required=True
    )

    fecha = fields.Date(
        string='Fecha', default=fields.Date.context_today
    )



    """referenciaSolCredito = fields.Many2one(
        'solcreditos.solcredito',
        string='Referencia a Solicitud de Crédito',
        help='Referencia a la solicitud de crédito asociada a este activo.'
    )"""


