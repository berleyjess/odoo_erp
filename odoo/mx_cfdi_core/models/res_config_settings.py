#mx_cfdi_core/models/res_config_settings.py
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mx_cfdi_provider = fields.Selection(
        selection=[
            ('mx.cfdi.engine.provider.dummy', 'Dummy (pruebas)'),
            ('mx.cfdi.engine.provider.base', 'Base (personalizado)'),
        ],
        string='Proveedor CFDI',
        config_parameter='mx_cfdi_engine.provider',
        default='mx.cfdi.engine.provider.dummy',
    )
