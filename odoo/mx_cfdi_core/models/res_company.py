# mx_cfdi_core/models/res_company_cfdi.py
from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    cfdi_provider = fields.Selection([
        ('mx.cfdi.engine.provider.dummy', 'Dummy (pruebas)'),
        ('mx.cfdi.engine.provider.sw', 'SW Sapien (REST)'),
    ], default='mx.cfdi.engine.provider.dummy')

    # SW (por empresa)
    cfdi_sw_sandbox      = fields.Boolean(default=True)
    cfdi_sw_base_url     = fields.Char()
    cfdi_sw_token        = fields.Char()
    cfdi_sw_user         = fields.Char()
    cfdi_sw_password     = fields.Char()
    cfdi_sw_rfc          = fields.Char()
    cfdi_sw_key_password = fields.Char()
    #cfdi_sw_cer_pem      = fields.Text()   # pega el PEM
    #cfdi_sw_key_pem      = fields.Text()   # pega el PEM

    cfdi_sw_cer_file     = fields.Binary(string="CSD Cert (.cer/.pem)", attachment=True)
    #cfdi_sw_cer_fname    = fields.Char(string="Nombre Certificado")
    cfdi_sw_key_file     = fields.Binary(string="CSD Key (.key/.pem)", attachment=True)
    #scfdi_sw_key_fname    = fields.Char(string="Nombre Llave")