# mx_cfdi_core/models/res_config_settings.py
from odoo import models, fields
"""
    Exposición en Ajustes del sistema para seleccionar el proveedor CFDI por defecto.
    El valor se guarda en el parámetro del sistema 'mx_cfdi_engine.provider' y el
    engine lo usa como fallback cuando la empresa no tiene un proveedor específico.
"""
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Guarda/lee de ICP: mx_cfdi_engine.provider (fallback usado por el engine)
    mx_cfdi_provider = fields.Selection([
        ('mx.cfdi.engine.provider.dummy', 'Dummy (pruebas)'),
        ('mx.cfdi.engine.provider.sw',    'SW Sapien (REST)'),
    ], string='Proveedor CFDI', config_parameter='mx_cfdi_engine.provider')