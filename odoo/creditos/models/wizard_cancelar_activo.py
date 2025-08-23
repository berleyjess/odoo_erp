# creditos/models/wizard_cancelar_activo.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class WizardCancelarActivo(models.TransientModel):
    _name = 'creditos.wizard.cancelar.activo'
    _description = 'Wizard para cancelar activos con motivo'

    activo_id = fields.Many2one(
        'activos.activo',
        string='Activo',
        required=True
    )
    
    motivo_cancelacion = fields.Text(
        string='Motivo de la Cancelación',
        required=True,
        help='Especifique el motivo por el cual se cancela el activo'
    )

    def action_confirmar_cancelacion(self):
        """Confirma la cancelación con el motivo especificado"""
        if not self.motivo_cancelacion.strip():
            raise ValidationError(_('Debe especificar un motivo para la cancelación.'))
            
        self.activo_id.action_cancelar_activo(self.motivo_cancelacion)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Activo Cancelado'),
                'message': _('El activo ha sido cancelado exitosamente.'),
                'type': 'warning',
                'sticky': False,
            }
        }