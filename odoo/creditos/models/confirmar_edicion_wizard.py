from odoo import models, fields

class ConfirmarEdicionWizard(models.TransientModel):
    _name = 'creditos.confirmar.edicion.wizard'
    _description = 'Wizard para confirmar edición de solicitud de crédito'

    mensaje = fields.Char(default="¿Estás seguro de que quieres editar esta solicitud?")

    def action_confirmar(self):
        active_id = self.env.context.get('active_id')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Editar Solicitud de Crédito',
            'res_model': 'creditos.credito',
            'res_id': active_id,
            'view_mode': 'form',
            'view_id': self.env.ref('creditos.view_credito_edit').id,
            'target': 'current',
        }
