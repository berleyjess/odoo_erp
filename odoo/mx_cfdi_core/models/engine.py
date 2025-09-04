# mx_cfdi_engine/models/engine.py
from odoo import models, api, _, fields
from odoo.exceptions import UserError
import base64
from xml.etree.ElementTree import Element, SubElement, tostring


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

    def _build_xml(self, **kw):
        tipo = kw.get('tipo') or 'I'
        receptor_id = kw.get('receptor_id')
        conceptos = kw.get('conceptos') or []
        uso_cfdi = kw.get('uso_cfdi') or 'G03'
        metodo = kw.get('metodo') or None
        forma = kw.get('forma') or None
        moneda = kw.get('moneda') or 'MXN'
        fecha = kw.get('fecha') or fields.Datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

        company = self.env.company
        cpostal = getattr(company, 'zip', None) or getattr(company, 'postal_code', None) or '00000'
        emisor_rfc = (getattr(company, 'vat', None) or '').upper() or 'EKU9003173C9'
        emisor_nombre = (getattr(company, 'name', None) or 'EMISOR').upper()

        total = 0.0
        subtotal = 0.0
        for c in conceptos:
            qty = float(c.get('cantidad') or c.get('qty') or 1.0)
            pu = float(c.get('valor_unitario') or c.get('price') or 0.0)
            imp = float(c.get('importe') or qty * pu)
            subtotal += qty * pu
            total += imp

        comprobante = Element('cfdi:Comprobante', {
            'Version': '4.0',
            'Fecha': fecha,
            'Moneda': moneda,
            'TipoDeComprobante': {'I': 'I', 'E': 'E', 'P': 'P'}.get(tipo, 'I'),
            'Exportacion': '01',
            'SubTotal': f"{subtotal:.2f}",
            'Total': f"{total:.2f}",
            'LugarExpedicion': cpostal,
            'xmlns:cfdi': 'http://www.sat.gob.mx/cfd/4',
        })
        SubElement(comprobante, 'cfdi:Emisor', {
            'Rfc': emisor_rfc,
            'Nombre': emisor_nombre,
            'RegimenFiscal': '601',
        })

        receptor = self.env['res.partner'].browse(receptor_id) if receptor_id else False
        rec_rfc = (receptor.vat or 'XAXX010101000').upper()
        rec_nombre = receptor.name or 'PUBLICO EN GENERAL'
        rec_cp = receptor.zip or '00000'
        SubElement(comprobante, 'cfdi:Receptor', {
            'Rfc': rec_rfc,
            'Nombre': rec_nombre,
            'UsoCFDI': uso_cfdi,
            'DomicilioFiscalReceptor': rec_cp,
            'RegimenFiscalReceptor': '601',
        })

        if tipo in ('I', 'E'):
            if metodo:
                comprobante.set('MetodoPago', metodo)
            if forma:
                comprobante.set('FormaPago', forma)

            cs = SubElement(comprobante, 'cfdi:Conceptos')
            for c in conceptos:
                SubElement(cs, 'cfdi:Concepto', {
                    'ClaveProdServ': c.get('clave_sat', '01010101'),
                    'NoIdentificacion': str(c.get('no_identificacion', '1')),
                    'Cantidad': f"{float(c.get('cantidad', 1.0)):.2f}",
                    'ClaveUnidad': c.get('clave_unidad', 'H87'),
                    'Descripcion': c.get('descripcion', 'Producto'),
                    'ValorUnitario': f"{float(c.get('valor_unitario', 0.0)):.2f}",
                    'Importe': f"{float(c.get('importe', 0.0)):.2f}",
                    'ObjetoImp': c.get('objeto_imp', '01'),
                })

        xml_bytes = tostring(comprobante, encoding='utf-8', xml_declaration=True)
        return xml_bytes

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

    @api.model
    def cancel_cfdi(self, *, origin_model, origin_id, uuid):
        provider = self._get_provider()
        params = self.env['ir.config_parameter'].sudo()
        rfc = params.get_param('mx_cfdi_sw.rfc') or (self.env.company.vat or '')
        cer_pem = params.get_param('mx_cfdi_sw.cer_pem')
        key_pem = params.get_param('mx_cfdi_sw.key_pem')
        password = params.get_param('mx_cfdi_sw.key_password')
        if not (uuid and rfc and cer_pem and key_pem):
            raise UserError(_('Faltan parámetros para cancelar: uuid/rfc/certificados.'))
        res = provider._cancel(uuid, rfc=rfc, cer_pem=cer_pem, key_pem=key_pem, password=password)
        doc = self.env['mx.cfdi.document'].search([('uuid', '=', uuid)], limit=1)
        if doc:
            doc.write({'state': 'canceled'})
        acuse = res.get('acuse') if isinstance(res, dict) else None
        if acuse:
            if isinstance(acuse, str):
                acuse = acuse.encode('utf-8')
            name = f"cancelacion-{uuid}.xml"
            self.env['ir.attachment'].sudo().create({
                'name': name,
                'res_model': origin_model,
                'res_id': origin_id,
                'type': 'binary',
                'datas': base64.b64encode(acuse),
                'mimetype': 'application/xml',
                'description': _('Acuse de cancelación %s') % (uuid,),
            })
        return res

