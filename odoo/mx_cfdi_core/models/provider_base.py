# mx_cfdi_engine/models/provider_base.py
from odoo import models, api, _
from odoo.exceptions import UserError

class CfdiProviderBase(models.AbstractModel):
    _name = "mx.cfdi.engine.provider.base"
    _description = "CFDI Provider Base"

    @api.model
    def _stamp_xml(self, xml_bytes):
        raise UserError(_("Implementa _stamp_xml en un módulo proveedor."))

    @api.model
    def _cancel(self, uuid, rfc=None, cer_pem=None, key_pem=None, password=None):
        raise UserError(_("Implementa _cancel en un proveedor."))

    @api.model
    def _status(self, uuid, rfc=None):
        raise UserError(_("Implementa _status en un proveedor."))

