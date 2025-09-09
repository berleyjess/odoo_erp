#mx_cfdi_provider_sw/models/res_config_settings.py
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Config simples (permitidas)
    mx_cfdi_sw_sandbox = fields.Boolean(string='SW Sandbox', default=True, config_parameter='mx_cfdi_sw.sandbox')
    mx_cfdi_sw_base_url = fields.Char(string='SW Base URL', config_parameter='mx_cfdi_sw.base_url')
    mx_cfdi_sw_token = fields.Char(string='SW Token', config_parameter='mx_cfdi_sw.token')
    mx_cfdi_sw_user = fields.Char(string='SW User', config_parameter='mx_cfdi_sw.user')
    mx_cfdi_sw_password = fields.Char(string='SW Password', config_parameter='mx_cfdi_sw.password')
    mx_cfdi_sw_rfc = fields.Char(string='RFC Emisor', config_parameter='mx_cfdi_sw.rfc')
    mx_cfdi_sw_key_password = fields.Char(string='CSD Key Password', config_parameter='mx_cfdi_sw.key_password')

    # PEM multilinea: NO usar config_parameter en Text
    mx_cfdi_sw_cer_pem = fields.Text(string='CSD Cert (PEM, pegar contenido)')
    mx_cfdi_sw_key_pem = fields.Text(string='CSD Key (PEM, pegar contenido)')


    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res.update({
            'mx_cfdi_sw_cer_pem': ICP.get_param('mx_cfdi_sw.cer_pem') or '',
            'mx_cfdi_sw_key_pem': ICP.get_param('mx_cfdi_sw.key_pem') or '',
        })
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        for rec in self:
            ICP.set_param('mx_cfdi_sw.cer_pem', rec.mx_cfdi_sw_cer_pem or '')
            ICP.set_param('mx_cfdi_sw.key_pem', rec.mx_cfdi_sw_key_pem or '')

    def action_test_sw(self):
        self.ensure_one()
        provider = self.env['mx.cfdi.engine.provider.sw']
        try:
            ok, msg = provider._ping()
        except Exception as e:
            ok, msg = False, str(e)
        color = 'success' if ok else 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'SW Sapien',
                'message': msg or ('Conexión correcta' if ok else 'No fue posible conectar'),
                'sticky': False,
                'type': color,
            }
        }
    
    def action_sw_upload_csd(self):
        self.ensure_one()
        self.env['mx.cfdi.engine.provider.sw']._upload_cert_from_config()
        return {'type':'ir.actions.client','tag':'display_notification',
                'params':{'title':'SW Sapien','message':'CSD cargado correctamente en SW.',
                          'type':'success','sticky':False}}

    def action_sw_check_cert(self):
        self.ensure_one()
        ok = self.env['mx.cfdi.engine.provider.sw']._has_cert(self.mx_cfdi_sw_rfc)
        return {'type':'ir.actions.client','tag':'display_notification',
                'params':{'title':'SW Sapien',
                          'message':('CSD encontrado' if ok else 'CSD NO encontrado'),
                          'type':('success' if ok else 'warning'),'sticky':False}}
