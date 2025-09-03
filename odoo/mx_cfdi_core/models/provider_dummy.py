#mx_cfdi_core/models/provider_dummy.py
from odoo import models
import uuid

class CfdiProviderDummy(models.AbstractModel):
    _name = "mx.cfdi.engine.provider.dummy"
    _inherit = "mx.cfdi.engine.provider.base"

    def _stamp_xml(self, xml_bytes):
        return {"uuid": str(uuid.uuid4()), "xml_timbrado": xml_bytes}
