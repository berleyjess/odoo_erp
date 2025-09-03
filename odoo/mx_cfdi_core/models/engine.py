# mx_cfdi_engine/models/engine.py
from odoo import models, api, _
from odoo.exceptions import UserError
import base64

class CfdiEngine(models.AbstractModel):
    _name = "mx.cfdi.engine"
    _description = "CFDI Engine (service)"

    @api.model
    def generate_and_stamp(self, *, origin_model, origin_id, tipo, receptor_id,
                           uso_cfdi=None, metodo=None, forma=None,
                           relacion_tipo=None, relacion_moves=None,
                           conceptos=None, moneda="MXN", serie=None, folio=None,
                           fecha=None, extras=None):

        xml = self._build_xml(tipo=tipo, receptor_id=receptor_id, conceptos=conceptos,
                              uso_cfdi=uso_cfdi, metodo=metodo, forma=forma,
                              relacion_tipo=relacion_tipo, relacion_moves=relacion_moves,
                              moneda=moneda, serie=serie, folio=folio, fecha=fecha,
                              extras=extras)

        provider = self._get_provider()
        stamped = provider._stamp_xml(xml)
        if not stamped or not stamped.get("uuid"):
            raise UserError(_("El PAC no devolvió un UUID."))

        doc = self.env["mx.cfdi.document"].create({
            "origin_model": origin_model,
            "origin_id": origin_id,
            "tipo": tipo,
            "uuid": stamped["uuid"],
            "xml": stamped.get("xml_timbrado"),
            "state": "stamped",
        })
        att = self._attach_xml(origin_model, origin_id, stamped.get("xml_timbrado"), doc)
        return {"uuid": doc.uuid, "attachment_id": att.id, "document_id": doc.id}

    # --- DUMMY BUILDER SOLO PARA PRUEBA ---
    def _build_xml(self, **kw):
        # Devuelve un XML mínimo para que el dummy "timbré"
        return b'<?xml version="1.0" encoding="UTF-8"?><Comprobante Version="DUMMY"/>'

    def _get_provider(self):
        provider_key = self.env['ir.config_parameter'].sudo().get_param(
            'mx_cfdi_engine.provider', default='mx.cfdi.engine.provider.dummy'
        )
        return self.env[provider_key]

    def _attach_xml(self, origin_model, origin_id, xml_bytes, doc):
        if not xml_bytes:
            raise UserError(_("No se recibió XML desde el proveedor."))
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode('utf-8')
        b64 = base64.b64encode(xml_bytes)
        name = f"{doc.uuid or 'cfdi'}-{origin_model.replace('.', '_')}-{origin_id}.xml"
        return self.env['ir.attachment'].sudo().create({
            'name': name,
            'res_model': origin_model,
            'res_id': origin_id,
            'type': 'binary',
            'datas': b64,
            'mimetype': 'application/xml',
            'description': _('CFDI timbrado %s') % (doc.uuid or ''),
        })
