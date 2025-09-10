# mx_cfdi_core/models/engine.py
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
        relacion_tipo = kw.get('relacion_tipo') or None
        relacion_moves = kw.get('relacion_moves') or None
        related_uuids_kw = kw.get('related_uuids') or []

        company = self.env.company
        cpostal = getattr(company, 'zip', None) or getattr(company, 'postal_code', None) or '00000'
        emisor_rfc = (company.cfdi_sw_rfc or company.vat or '').upper()
        if not emisor_rfc:
            raise UserError(_("Configura el RFC de la compañía."))

        rfc_cfg = (company.cfdi_sw_rfc or
           self.env['ir.config_parameter'].sudo().get_param('mx_cfdi_sw.rfc') or
           emisor_rfc)
        if rfc_cfg and rfc_cfg != emisor_rfc:
            raise UserError(_("El RFC de la compañía (%s) y el de Ajustes (%s) no coinciden.")
                            % (emisor_rfc, rfc_cfg))
        emisor_nombre  = (company.name or 'EMISOR').upper()
        emisor_regimen = getattr(company, 'l10n_mx_edi_fiscal_regime', None) or '601'

        total = 0.0
        subtotal = 0.0
        for c in conceptos:
            qty = float(c.get('cantidad') or c.get('qty') or 1.0)
            pu = float(c.get('valor_unitario') or c.get('price') or 0.0)
            imp = float(c.get('importe') or qty * pu)
            subtotal += qty * pu
            total += imp

        # >>> Emisión Timbrado: Sello/Certificado/NoCertificado VACÍOS
        comprobante = Element('cfdi:Comprobante', {
            'Version': '4.0',
            'Fecha': fecha,
            'Moneda': moneda,
            'TipoDeComprobante': {'I': 'I', 'E': 'E', 'P': 'P'}.get(tipo, 'I'),
            'Exportacion': '01',
            'SubTotal': f"{subtotal:.2f}",
            'Total': f"{total:.2f}",
            'LugarExpedicion': cpostal,
            'Sello': '',
            'Certificado': '',
            'NoCertificado': '',
            'xmlns:cfdi': 'http://www.sat.gob.mx/cfd/4',
        })
        SubElement(comprobante, 'cfdi:Emisor', {
            'Rfc': emisor_rfc,
            'Nombre': emisor_nombre,
            'RegimenFiscal': str(emisor_regimen),
        })

                # --- Receptor (una sola vez) con reglas de RFC genérico ---
        receptor = self.env['res.partner'].browse(receptor_id) if receptor_id else False
        rec_rfc = (getattr(receptor, 'vat', '') or '').strip().upper() or 'XAXX010101000'
        is_generic = rec_rfc in ('XAXX010101000', 'XEXX010101000')

        # Nombre / Uso / Régimen / CP conforme a reglas de global y RFC genérico
        rec_nombre  = 'PUBLICO EN GENERAL' if is_generic else (getattr(receptor, 'name', None) or 'CLIENTE')
        uso_cfdi_ok = 'S01' if is_generic else (kw.get('uso_cfdi') or 'G03')
        rec_regimen = '616' if is_generic else (getattr(receptor, 'l10n_mx_edi_fiscal_regime', None) or '601')
        rec_cp      = (cpostal if is_generic else (getattr(receptor, 'zip', None) or '00000'))

        SubElement(comprobante, 'cfdi:Receptor', {
            'Rfc': rec_rfc,
            'Nombre': rec_nombre,
            'UsoCFDI': uso_cfdi_ok,
            'DomicilioFiscalReceptor': rec_cp,
            'RegimenFiscalReceptor': str(rec_regimen),
        })


        # >>> BLOQUE NUEVO: reglas CFDI 4.0 para RFC genérico
        if rec_rfc in ('XAXX010101000', 'XEXX010101000'):
            uso_cfdi = 'S01'                # Sin obligaciones fiscales
            rec_regimen = '616'             # Sin obligaciones fiscales
            rec_nombre = 'PUBLICO EN GENERAL'
            rec_cp = cpostal                 # CP receptor = LugarExpedicion del emisor (requerido en global)

        SubElement(comprobante, 'cfdi:Receptor', {
            'Rfc': rec_rfc,
            'Nombre': rec_nombre,
            'UsoCFDI': uso_cfdi,
            'DomicilioFiscalReceptor': rec_cp,
            'RegimenFiscalReceptor': str(rec_regimen),
        })

        # Relaciones CFDI (egresos/sustitución/etc.)
        related_uuids = list(related_uuids_kw)
        if relacion_moves:
            for rm in relacion_moves:
                if getattr(rm, 'l10n_mx_edi_cfdi_uuid', False):
                    related_uuids.append(rm.l10n_mx_edi_cfdi_uuid)
        if relacion_tipo and related_uuids:
            rel = SubElement(comprobante, 'cfdi:CfdiRelacionados', {'TipoRelacion': relacion_tipo})
            for u in related_uuids:
                SubElement(rel, 'cfdi:CfdiRelacionado', {'UUID': u})

        if tipo in ('I', 'E'):
            if metodo:
                comprobante.set('MetodoPago', metodo)
            # Para PPD la forma suele ser '99' (por definir); para PUE, la forma real (01,03,...), si la envías.
            if forma:
                comprobante.set('FormaPago', forma)

            cs = SubElement(comprobante, 'cfdi:Conceptos')
            tot_tras = 0.0
            for c in conceptos:
                imp_obj = c.get('objeto_imp', '01')  # 01=No objeto, 02=Sí objeto, 03=Sí objeto y no obligado
                qty = float(c.get('cantidad', 1.0))
                vu = float(c.get('valor_unitario', 0.0))
                imp = float(c.get('importe', qty * vu))
                nodo = SubElement(cs, 'cfdi:Concepto', {
                    'ClaveProdServ': c.get('clave_sat', '01010101'),
                    'NoIdentificacion': str(c.get('no_identificacion', '1')),
                    'Cantidad': f"{qty:.2f}",
                    'ClaveUnidad': c.get('clave_unidad', 'H87'),
                    'Descripcion': c.get('descripcion', 'Producto'),
                    'ValorUnitario': f"{vu:.2f}",
                    'Importe': f"{imp:.2f}",
                    'ObjetoImp': imp_obj,
                })
                if imp_obj in ('02', '03'):
                    iva = float(c.get('iva', 0.0) or 0.0)   # ratio 0.160000 etc.
                    ieps = float(c.get('ieps', 0.0) or 0.0)
                    if iva or ieps:
                        imps = SubElement(nodo, 'cfdi:Impuestos')
                        tras = SubElement(imps, 'cfdi:Traslados')
                        if iva:
                            base = imp
                            imp_monto = round(base * iva, 2)
                            tot_tras += imp_monto
                            SubElement(tras, 'cfdi:Traslado', {
                                'Base': f"{base:.2f}",
                                'Impuesto': '002',
                                'TipoFactor': 'Tasa',
                                'TasaOCuota': f"{iva:.6f}",
                                'Importe': f"{imp_monto:.2f}",
                            })
                        if ieps:
                            base = imp
                            imp_monto = round(base * ieps, 2)
                            tot_tras += imp_monto
                            SubElement(tras, 'cfdi:Traslado', {
                                'Base': f"{base:.2f}",
                                'Impuesto': '003',
                                'TipoFactor': 'Tasa',
                                'TasaOCuota': f"{ieps:.6f}",
                                'Importe': f"{imp_monto:.2f}",
                            })
            if tot_tras:
                SubElement(comprobante, 'cfdi:Impuestos', {
                    'TotalImpuestosTrasladados': f"{tot_tras:.2f}"
                })

        xml_bytes = tostring(comprobante, encoding='utf-8', xml_declaration=True)
        return xml_bytes

    def _get_provider(self):
        # lee siempre el provider de la compañía actual del env
        provider_key = self.env.company.cfdi_provider or \
                       self.env['ir.config_parameter'].sudo().get_param('mx_cfdi_engine.provider', 'mx.cfdi.engine.provider.dummy')
        return self.env[provider_key].with_company(self.env.company)


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
    def cancel_cfdi(self, *, origin_model, origin_id, uuid, motivo='02', folio_sustitucion=None):
        provider = self._get_provider()
        company = self.env.company
        rfc = (company.cfdi_sw_rfc or company.vat or '').upper()
        cer_pem = company.cfdi_sw_cer_pem
        key_pem = company.cfdi_sw_key_pem
        password = company.cfdi_sw_key_password
        if not (uuid and rfc and cer_pem and key_pem):
            raise UserError(_('Faltan parámetros para cancelar: uuid/rfc/certificados.'))

        res = provider._cancel(uuid, rfc=rfc, cer_pem=cer_pem, key_pem=key_pem,
                           password=password, motivo=motivo, folio_sustitucion=folio_sustitucion)
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
