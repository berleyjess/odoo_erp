#mx_cfdi_core/models/provider_dummy.py
from odoo import models
import uuid
"""
    Proveedor de prueba (dummy). No llama a ningún PAC real.
    Genera un UUID aleatorio y regresa el mismo XML recibido como 'xml_timbrado'.
    Útil para pruebas de flujo sin dependencia externa del timbrado.
"""
class CfdiProviderDummy(models.AbstractModel):
    _name = "mx.cfdi.engine.provider.dummy"
    _inherit = "mx.cfdi.engine.provider.base"

    # Simula el timbrado devolviendo:
    #   {'uuid': <UUID aleatorio>, 'xml_timbrado': xml_bytes}
    # No valida ni firma el XML; solo para entornos de desarrollo/pruebas.
    def _stamp_xml(self, xml_bytes):
        return {"uuid": str(uuid.uuid4()), "xml_timbrado": xml_bytes}
