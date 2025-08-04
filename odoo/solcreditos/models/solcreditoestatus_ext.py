from odoo import models, fields, api

class SolCreditoEstatusExt(models.Model):
    _inherit = 'solcreditoestatus.estatu'  
    

    solcreditoestatu_id = fields.Many2one(
        'solcreditoestatus.solcreditoestatu',
        string="Estatus relacionado",
        help="Referencia a otro estatus de crédito relacionado."
    )
    
    def action_habilitar(self):
        for rec in self:
            rec.status = '1'

    def action_deshabilitar(self):
        for rec in self:
            rec.status = '0'

    def action_toggle_status(self):
        for rec in self:
            rec.status = '1' if rec.status == '0' else '0'