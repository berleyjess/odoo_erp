# creditos/models/credito_autorizacion_ext.py
from odoo import models, fields, api

class autorizados(models.Model):
    _name = 'creditos.autorizacion'
    #_inherit = 'creditoautorizaciones.autorizacion'  # Hereda del modelo de autorizaciones

    status = fields.Selection(string = "Dictamen", selection=[
        ('1', 'Aprobado'),
        ('2', 'Rechazado')
    ], required = True, default = '2')

    descripcion = fields.Char(
        string='Descripción',
        help='Descripción del status actual. Puede ser un texto breve que explique el estado del activo.', required=True
    )

    fecha = fields.Date(
        string='Fecha',
        help='Fecha en la que se registró el estado del status.',
        default=fields.Date.context_today, readonly=True

    )

    credito_id = fields.Many2one(
        'creditos.credito',
        string='Solicitud',
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