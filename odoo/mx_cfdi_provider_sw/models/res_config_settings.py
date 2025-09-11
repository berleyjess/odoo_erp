#mx_cfdi_provider_sw/models/res_config_settings.py
from odoo import models, fields, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- tus campos planos, como ya los tienes ---
    mx_cfdi_provider        = fields.Selection([
        ('mx.cfdi.engine.provider.dummy', 'Dummy (pruebas)'),
        ('mx.cfdi.engine.provider.sw',    'SW Sapien (REST)'),
    ], string='Proveedor CFDI')
    mx_cfdi_sw_sandbox      = fields.Boolean(string='SW Sandbox')
    mx_cfdi_sw_base_url     = fields.Char(string='SW Base URL')
    mx_cfdi_sw_token        = fields.Char(string='SW Token')
    mx_cfdi_sw_user         = fields.Char(string='SW Usuario')
    mx_cfdi_sw_password     = fields.Char(string='SW Password')
    mx_cfdi_sw_rfc          = fields.Char(string='RFC Emisor')
    mx_cfdi_sw_key_password = fields.Char(string='CSD Password')
    #mx_cfdi_sw_cer_pem      = fields.Text(string='CER (PEM)')
    #mx_cfdi_sw_key_pem      = fields.Text(string='KEY (PEM)')

    mx_cfdi_sw_cer_file  = fields.Binary(string='CSD Cert (.cer/.pem)')
    #mx_cfdi_sw_cer_fname = fields.Char(string='Nombre Cert')
    mx_cfdi_sw_key_file  = fields.Binary(string='CSD Key (.key/.pem)')
    #mx_cfdi_sw_key_fname = fields.Char(string='Nombre Key')
    def get_values(self):
        res = super().get_values()
        c = self.env.company
        res.update({
            'mx_cfdi_provider':        c.cfdi_provider,
            'mx_cfdi_sw_sandbox':      c.cfdi_sw_sandbox,
            'mx_cfdi_sw_base_url':     c.cfdi_sw_base_url,
            'mx_cfdi_sw_token':        c.cfdi_sw_token,
            'mx_cfdi_sw_user':         c.cfdi_sw_user,
            'mx_cfdi_sw_password':     c.cfdi_sw_password,
            'mx_cfdi_sw_rfc':          c.cfdi_sw_rfc,
            'mx_cfdi_sw_key_password': c.cfdi_sw_key_password,
            'mx_cfdi_sw_cer_file':     c.cfdi_sw_cer_file,
            #'mx_cfdi_sw_cer_fname':    c.cfdi_sw_cer_fname,
            'mx_cfdi_sw_key_file':     c.cfdi_sw_key_file,
            #'mx_cfdi_sw_key_fname':    c.cfdi_sw_key_fname,
        })
        return res

    def set_values(self):
        super().set_values()
        c = self.env.company
        c.write({
            'cfdi_provider':        self.mx_cfdi_provider,
            'cfdi_sw_sandbox':      self.mx_cfdi_sw_sandbox,
            'cfdi_sw_base_url':     self.mx_cfdi_sw_base_url,
            'cfdi_sw_token':        self.mx_cfdi_sw_token,
            'cfdi_sw_user':         self.mx_cfdi_sw_user,
            'cfdi_sw_password':     self.mx_cfdi_sw_password,
            'cfdi_sw_rfc':          self.mx_cfdi_sw_rfc,
            'cfdi_sw_key_password': self.mx_cfdi_sw_key_password,
            'cfdi_sw_cer_file':     self.mx_cfdi_sw_cer_file,
            #'cfdi_sw_cer_fname':    self.mx_cfdi_sw_cer_fname,
            'cfdi_sw_key_file':     self.mx_cfdi_sw_key_file,
            #'cfdi_sw_key_fname':    self.mx_cfdi_sw_key_fname,
        })

    # --- BOTONES QUE USA LA VISTA ---
    def action_test_sw(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        ok, msg = self.env['mx.cfdi.engine.provider.sw'].with_company(company)._ping()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': 'SW Sapien',
                       'message': msg or ('Conexión OK' if ok else 'No fue posible conectar'),
                       'type': 'success' if ok else 'danger',
                       'sticky': False}
        }

    def action_sw_upload_csd(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        self.env['mx.cfdi.engine.provider.sw'].with_company(company)._upload_cert_from_company()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'SW Sapien', 'message': 'CSD cargado correctamente en SW.',
                           'type': 'success', 'sticky': False}}

    def action_sw_check_cert(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        ok = self.env['mx.cfdi.engine.provider.sw'].with_company(company)._has_cert(self.mx_cfdi_sw_rfc)
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'SW Sapien',
                           'message': ('CSD encontrado' if ok else 'CSD NO encontrado'),
                           'type': ('success' if ok else 'warning'), 'sticky': False}}
