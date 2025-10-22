#mx_cfdi_provider_sw/models/res_config_settings.py
from odoo import models, fields, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mx_cfdi_provider        = fields.Selection(
        [('mx.cfdi.engine.provider.dummy','Dummy'),
         ('mx.cfdi.engine.provider.sw','SW Sapien')], string='Proveedor CFDI',
        config_parameter='mx_cfdi.provider')

    mx_cfdi_sw_sandbox      = fields.Boolean(config_parameter='mx_cfdi_sw.sandbox')
    mx_cfdi_sw_base_url     = fields.Char(config_parameter='mx_cfdi_sw.base_url')
    mx_cfdi_sw_token        = fields.Char(config_parameter='mx_cfdi_sw.token')
    mx_cfdi_sw_user         = fields.Char(config_parameter='mx_cfdi_sw.user')
    mx_cfdi_sw_password     = fields.Char(config_parameter='mx_cfdi_sw.password')
    mx_cfdi_sw_key_password = fields.Char(config_parameter='mx_cfdi_sw.key_password')


    # Botón de “Probar conexión” para SW Sapien.
    # - Toma una empresa (la primera encontrada) y pone empresa_id en el contexto.
    # - Llama al método _ping() del proveedor SW para verificar conectividad.
    # - Muestra una notificación en la UI con el resultado (éxito/error).

    def action_test_sw(self):
        self.ensure_one()
        empresa = self.env['empresas.empresa'].search([], limit=1)
        
        ok, msg = self.env['mx.cfdi.engine.provider.sw'].with_context(empresa_id=empresa.id)._ping()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': 'SW Sapien',
                       'message': msg or ('Conexión OK' if ok else 'No fue posible conectar'),
                       'type': 'success' if ok else 'danger',
                       'sticky': False}
        }

    