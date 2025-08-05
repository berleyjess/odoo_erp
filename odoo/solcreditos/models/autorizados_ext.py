# solcreditos/models/solcredito_autorizacion_ext.py
from odoo import models, fields, api

class autorizados_ext(models.Model):
    _name = 'solcreditos.autorizacion_ext'
    _inherit = 'solcreditoautorizaciones.autorizacion'  # Hereda del modelo de autorizaciones

    autorizacion_id = fields.Many2one(
        'solcreditos.solcredito',
        string='Autorización',
        ondelete='cascade'
    )

    def is_autorizada(self):
        """Método para saber si está aprobada"""
        self.ensure_one()
        return self.autorizacion_id and self.autorizacion_id.statusAutorizacion == '1'

    def action_view_autorizacion(self):
        """Ver la autorización relacionada"""
        self.ensure_one()
        if self.autorizacion_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'autorizaciones.autorizacion',
                'view_mode': 'form',
                'res_id': self.autorizacion_id.id,
                'target': 'current',
                'context': {'form_view_ref': 'autorizaciones.view_autorizacion_form'}
            }