# autorizaciones/models/wizard_rechazo.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class WizardRechazo(models.TransientModel):
    _name = 'solcreditoautorizaciones.wizard.rechazo'
    _description = 'Wizard para rechazar autorizaciones con motivo'

    autorizacion_id = fields.Many2one(
        'solcreditoautorizaciones.autorizacion',
        string='Autorización',
        required=True
    )
    
    motivo_rechazo = fields.Text(
        string='Motivo del Rechazo',
        required=True,
        help='Especifique el motivo por el cual se rechaza la autorización'
    )

    def action_confirmar_rechazo(self):
        """Confirma el rechazo con el motivo especificado"""
        if not self.motivo_rechazo.strip():
            raise ValidationError(_('Debe especificar un motivo para el rechazo.'))
            
        self.autorizacion_id._rechazar_con_motivo(self.motivo_rechazo)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Autorización Rechazada'),
                'message': _('La solicitud ha sido rechazada exitosamente.'),
                'type': 'warning',
                'sticky': False,
            }
        }