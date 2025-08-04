# solcreditos/models/solcredito_autorizacion_ext.py
from odoo import models, fields, api

class SolCreditoAutorizacionExt(models.Model):
    _inherit = 'solcreditos.solcredito'

    autorizacion_id = fields.Many2one(
        'autorizaciones.autorizacion',
        string='Autorización',
        help='Autorización vinculada a la solicitud',
        readonly=True
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