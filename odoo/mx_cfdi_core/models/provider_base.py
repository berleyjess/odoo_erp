# mx_cfdi_engine/models/provider_base.py
from odoo import models, api, _
from odoo.exceptions import UserError

class CfdiProviderBase(models.AbstractModel):
    _name = "mx.cfdi.engine.provider.base"
    _description = "CFDI Provider Base"

    @api.model
    def _stamp_xml(self, xml_bytes):
        raise UserError(_("Implementa _stamp_xml en un módulo proveedor."))

