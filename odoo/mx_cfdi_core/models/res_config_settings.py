# mx_cfdi_core/models/res_config_settings.py
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Campo PLANO en el wizard (sin related)
    mx_cfdi_provider = fields.Selection([
        ('mx.cfdi.engine.provider.dummy', 'Dummy (pruebas)'),
        ('mx.cfdi.engine.provider.sw',    'SW Sapien (REST)'),
    ], string='Proveedor CFDI')

    def get_values(self):
        res = super().get_values()
        c = self.env.company
        res.update({
            'mx_cfdi_provider': c.cfdi_provider,
        })
        return res

    def set_values(self):
        super().set_values()
        c = self.env.company
        c.cfdi_provider = self.mx_cfdi_provider
