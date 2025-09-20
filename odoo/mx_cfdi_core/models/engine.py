# mx_cfdi_core/models/engine.py
from odoo import models, api, _, fields
from odoo.exceptions import UserError
import base64
from xml.etree.ElementTree import Element, SubElement, tostring
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)
from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace
register_namespace('cfdi', 'http://www.sat.gob.mx/cfd/4')
register_namespace('xsi',  'http://www.w3.org/2001/XMLSchema-instance')

class CfdiEngine(models.AbstractModel):
    _name = "mx.cfdi.engine"
    _description = "CFDI Engine (service)"

    @staticmethod
    def _is_moral_rfc(rfc: str) -> bool:
        rfc = (rfc or '').strip().upper()
        if rfc in ('XAXX010101000', 'XEXX010101000'):
            return False
        return len(rfc) == 12

    @api.model
    def generate_and_stamp(self, *, origin_model, origin_id, tipo, receptor_id,
                           uso_cfdi=None, metodo=None, forma=None,
                           relacion_tipo=None, relacion_moves=None,
                           conceptos=None, moneda="MXN", serie=None, folio=None,
                           fecha=None, extras=None):
        _logger.info("CFDI DEBUG | generate_and_stamp IN: model=%s id=%s tipo=%s receptor_id=%s fecha_arg=%s",
                     origin_model, origin_id, tipo, receptor_id, fecha)
        xml = self._build_xml(tipo=tipo, receptor_id=receptor_id, conceptos=conceptos,
                              uso_cfdi=uso_cfdi, metodo=metodo, forma=forma,
                              relacion_tipo=relacion_tipo, relacion_moves=relacion_moves,
                              moneda=moneda, serie=serie, folio=folio, fecha=fecha,
                              extras=extras)

        provider = self._get_provider()
        _logger.info("CFDI DEBUG | provider=%s company_id=%s", provider._name, self.env.company.id)

        # 2) Timbrar + reintento si se detecta 305
        stamped = None
        saw_305 = False
        try:
            stamped = provider._stamp_xml(xml)
        except Exception as e:
            if self._is_305(exc=e):
                _logger.warning("CFDI DEBUG | 305 detectado vía excepción: %s", e)
                saw_305 = True
            else:
                raise
            
        # Si vimos 305 por excepción o por payload, reintentar con Fecha UTC “plana”
        if saw_305 or self._is_305(payload=stamped):
            fecha_utc = fields.Datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            _logger.warning("CFDI DEBUG | Reintentando 305 con FECHA UTC=%s", fecha_utc)
            xml = self._build_xml(tipo=tipo, receptor_id=receptor_id, conceptos=conceptos,
                                  uso_cfdi=uso_cfdi, metodo=metodo, forma=forma,
                                  relacion_tipo=relacion_tipo, relacion_moves=relacion_moves,
                                  moneda=moneda, serie=serie, folio=folio, fecha=fecha_utc,
                                  extras=extras)
            stamped = provider._stamp_xml(xml)


        if not stamped or not stamped.get("uuid"):
            # Si seguimos sin UUID, deja claro en log qué devolvió el PAC
            _logger.error("CFDI DEBUG | PAC sin UUID. Payload=%s", stamped)
            raise UserError(_("El PAC no devolvió un UUID."))

        # Fallback: si por alguna razón no vino el XML, bájalo del DW por UUID
        if not stamped.get("xml_timbrado"):
            try:
                dl = provider.download_xml_by_uuid(stamped['uuid'], tries=10, delay=1.0)
                stamped['xml_timbrado'] = dl.get('xml')
                # opcional: guardar acuse de timbrado como attachment separado
                if dl.get('acuse'):
                    self.env['ir.attachment'].sudo().create({
                        'name': f"acuse-{stamped['uuid']}.xml",
                        'res_model': origin_model,
                        'res_id': origin_id,
                        'type': 'binary',
                        'datas': base64.b64encode(dl['acuse']),
                        'mimetype': 'application/xml',
                        'description': _('Acuse CFDI %s (SW DW)') % (stamped['uuid'],),
                    })
            except Exception as e:
                _logger.warning("CFDI DEBUG | No se pudo recuperar XML por UUID: %s", e)
                _logger.info("CFDI DEBUG | provider returned keys=%s", list(stamped.keys()))


        xml_bytes = stamped.get("xml_timbrado")
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode("utf-8")

        xml_b64 = base64.b64encode(xml_bytes).decode("ascii")

        doc = self.env["mx.cfdi.document"].create({
            "origin_model": origin_model,
            "origin_id": origin_id,
            "tipo": tipo,
            "uuid": stamped["uuid"],
            "xml": xml_b64,                # <-- ahora sí, Base64 (str)
            "state": "stamped",
        })
        att = self._attach_xml(origin_model, origin_id, stamped.get("xml_timbrado"), doc)
        _logger.info("CFDI DEBUG | stamped uuid=%s | att_id=%s | doc_id=%s", doc.uuid, att.id, doc.id)
        return {"uuid": doc.uuid, "attachment_id": att.id, "document_id": doc.id}

    @staticmethod
    def _legal_name(p):
        name = (getattr(p, 'l10n_mx_edi_legal_name', None) or getattr(p, 'name', None) or '').strip()
        # NO toques signos; solo colapsa espacios y mayúsculas
        return ' '.join(name.split()).upper()

    @api.model
    def _build_xml(self, **kw):
        """
        FIX #1: Receptor solo una vez (sin duplicar nodo).
        FIX #2: Importes correctos (Importe = Cantidad x ValorUnitario sin impuestos),
                SubTotal/Total bien calculados y TotalImpuestosTrasladados.
        """
        tipo         = kw.get('tipo') or 'I'
        receptor_id  = kw.get('receptor_id')
        conceptos_in = kw.get('conceptos') or []
        uso_default  = kw.get('uso_cfdi') or 'G03'
        metodo       = kw.get('metodo') or None
        forma        = kw.get('forma') or None
        moneda       = kw.get('moneda') or 'MXN'
        
        #Fecha a zona del usuario (o MX por defecto) para no salirte de la vigencia del CSD:
        if kw.get('fecha'):
            fecha = str(kw['fecha']).strip().replace(' ', 'T')[:19]
        else:
            fecha = self._as_cfdi_fecha(self._mx_local_now())

        #fecha='2025-09-17T10:20:00'  # hora local MX
        relacion_tipo   = kw.get('relacion_tipo') or None
        relacion_moves  = kw.get('relacion_moves') or None
        related_uuids_kw= kw.get('related_uuids') or []

        company = self.env.company
        cpostal = (company.partner_id.zip or getattr(company, 'zip', None)
                   or getattr(company, 'postal_code', None) or '').strip()
        if not cpostal or cpostal == '00000':
            _logger.warning("CFDI DEBUG | LugarExpedicion sin CP real; usando '01000' temporalmente.")
            cpostal = '01000'

        # trazas de fecha/tz/cp
        self._debug_dates(fecha, cpostal)

        # === CAMBIO 3: RFC del emisor SOLO del campo fiscal (evita fallback involuntario) ===
        emisor_rfc = (company.cfdi_sw_rfc or '').upper()
        if not emisor_rfc:
            raise UserError(_("Configura el RFC Emisor (cfdi_sw_rfc) y carga su CSD en SW."))
        _logger.info("CFDI DEBUG | EMISOR RFC=%s company_id=%s", emisor_rfc, company.id)

        is_moral = self._is_moral_rfc(emisor_rfc)

        # Toma el configurado si existe; si no, default correcto por tipo de persona
        reg_cfg = getattr(company, 'l10n_mx_edi_fiscal_regime', None)
        if not reg_cfg:
            reg_cfg = '601' if is_moral else '612'   # 601=PM; 612=PF con AE/Prof (válido para PF)

        # Validación suave: evita régimen de PM con RFC de PF y viceversa
        PM_CODES = {'601','603','620','623','624','628'}     # (suficiente para evitar el error del PAC)
        PF_CODES = {'605','606','607','608','611','612','614','615','616'}

        if is_moral and reg_cfg in PF_CODES:
            raise UserError(_("El RFC %(rfc)s es de Persona Moral (12 dígitos) pero el régimen %(reg)s es de Persona Física. "
                              "Corrige el 'Régimen Fiscal' en la compañía fiscal.")
                            % {'rfc': emisor_rfc, 'reg': reg_cfg})
        if (not is_moral) and reg_cfg in PM_CODES:
            raise UserError(_("El RFC %(rfc)s es de Persona Física (13 dígitos) pero el régimen %(reg)s es de Persona Moral. "
                              "Corrige el 'Régimen Fiscal' en la compañía fiscal.")
                            % {'rfc': emisor_rfc, 'reg': reg_cfg})

        emisor_regimen = reg_cfg
        emisor_nombre  = (getattr(company, 'l10n_mx_edi_legal_name', None)
                          or company.partner_id.name
                          or company.name
                          or 'EMISOR').strip().upper()


        # --- Precalcular importes correctamente a partir de los conceptos recibidos ---
        subtotal_sum = 0.0
        traslados_total = 0.0

        conceptos_calc = []
        for c in conceptos_in:
            qty = float(c.get('cantidad') or c.get('qty') or 1.0)
            vu  = float(c.get('valor_unitario') or c.get('price') or 0.0)

            base = round(qty * vu, 2)              # <- importe del concepto SIN impuestos
            subtotal_sum += base

            #imp_obj = c.get('objeto_imp', '01')    # 01=No objeto, 02=Sí objeto, 03=Sí objeto y no obligado
            iva_ratio  = float(c.get('iva') or 0.0)
            ieps_ratio = float(c.get('ieps') or 0.0)
            imp_obj = (c.get('objeto_imp') or
                        ('02' if (iva_ratio or ieps_ratio or (c.get('impuestos') and (c['impuestos'].get('traslados') or [])))
                         else '01'))

            # Permitir también estructura anidada c['impuestos']['traslados'] si ya viene calculada
            traslados = []
            if imp_obj in ('02', '03'):
                if c.get('impuestos') and isinstance(c['impuestos'], dict):
                    for t in (c['impuestos'].get('traslados') or []):
                        t_base   = float(t.get('base', base) or base)
                        t_imp    = float(t.get('importe') or 0.0)
                        t_code   = str(t.get('impuesto') or '')
                        t_factor = str(t.get('tipo_factor') or 'Tasa')
                        t_tasa   = t.get('tasa_cuota')
                        if t_imp and t_code in ('002', '003'):
                            traslados_total += t_imp
                            entry = {'Base': f"{t_base:.2f}", 'Impuesto': t_code,
                                     'TipoFactor': t_factor}
                            if t_tasa is not None:
                                entry['TasaOCuota'] = f"{float(t_tasa):.6f}"
                            entry['Importe'] = f"{t_imp:.2f}"
                            traslados.append(entry)
                else:
                    # Calcular rápido por tasas (iva/ieps) si vinieron como ratios
                    if iva_ratio:
                        iva_imp = round(base * iva_ratio, 2)
                        traslados_total += iva_imp
                        traslados.append({
                            'Base': f"{base:.2f}", 'Impuesto': '002',
                            'TipoFactor': 'Tasa', 'TasaOCuota': f"{iva_ratio:.6f}",
                            'Importe': f"{iva_imp:.2f}",
                        })
                    if ieps_ratio:
                        ieps_imp = round(base * ieps_ratio, 2)
                        traslados_total += ieps_imp
                        traslados.append({
                            'Base': f"{base:.2f}", 'Impuesto': '003',
                            'TipoFactor': 'Tasa', 'TasaOCuota': f"{ieps_ratio:.6f}",
                            'Importe': f"{ieps_imp:.2f}",
                        })

            conceptos_calc.append({
                'base': base,
                'imp_obj': imp_obj,
                'qty': qty,
                'vu': vu,
                'clave_sat': c.get('clave_sat', '01010101'),
                'no_ident': str(c.get('no_identificacion', c.get('no_ident') or '1')),
                'clave_unidad': c.get('clave_unidad', 'H87'),
                'descripcion': c.get('descripcion', 'Producto'),
                'traslados': traslados,
            })

        total_sum = round(subtotal_sum + traslados_total, 2)

        # --- Comprobante ---
        comprobante = Element('cfdi:Comprobante', {
            'Version': '4.0',
            'Fecha': fecha,
            'Moneda': moneda,
            'TipoDeComprobante': {'I':'I','E':'E','P':'P'}.get(tipo, 'I'),
            'Exportacion': '01',
            'SubTotal': f"{subtotal_sum:.2f}",
            'Total': f"{total_sum:.2f}",
            'LugarExpedicion': cpostal,
            'Sello': '',
            'Certificado': '',
            'NoCertificado': '',
            # namespaces requeridos:
            'xmlns:cfdi': 'http://www.sat.gob.mx/cfd/4',
            'xmlns:xsi':  'http://www.w3.org/2001/XMLSchema-instance',
            'xsi:schemaLocation': 'http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd',
        })


        # Emisor
        SubElement(comprobante, 'cfdi:Emisor', {
            'Rfc': emisor_rfc,
            'Nombre': emisor_nombre,
            'RegimenFiscal': str(emisor_regimen),
        })

        # Receptor (UNA sola vez) con reglas de RFC genérico
        receptor = self.env['res.partner'].browse(receptor_id) if receptor_id else False
        rec_rfc = (getattr(receptor, 'vat', '') or '').strip().upper() or 'XAXX010101000'
        is_generic = rec_rfc in ('XAXX010101000', 'XEXX010101000')

        if is_generic:
            rec_regimen = '616'
        else:
            rec_regimen = getattr(receptor, 'l10n_mx_edi_fiscal_regime', None)
            if not rec_regimen:
                rec_regimen = '601' if self._is_moral_rfc(rec_rfc) else '612' # PM vs PF "seguro"
    
        # Nombre exacto (usa l10n_mx_edi_legal_name si existe), colapsando espacios:
        rec_nombre = 'PUBLICO EN GENERAL' if is_generic else (self._legal_name(receptor) or 'CLIENTE')
        
        uso_cfdi_ok = 'S01' if is_generic else uso_default
        #rec_regimen = '616' if is_generic else (getattr(receptor, 'l10n_mx_edi_fiscal_regime', None) or '601')
        rec_cp      = (cpostal if is_generic else (getattr(receptor, 'zip', None) or '00000'))

        SubElement(comprobante, 'cfdi:Receptor', {
            'Rfc': rec_rfc,
            'Nombre': rec_nombre,
            'UsoCFDI': uso_cfdi_ok,
            'DomicilioFiscalReceptor': rec_cp,
            'RegimenFiscalReceptor': str(rec_regimen),
        })

        # Relaciones CFDI
        related_uuids = list(related_uuids_kw)
        if relacion_moves:
            for rm in relacion_moves:
                if getattr(rm, 'l10n_mx_edi_cfdi_uuid', False):
                    related_uuids.append(rm.l10n_mx_edi_cfdi_uuid)
        if relacion_tipo and related_uuids:
            rel = SubElement(comprobante, 'cfdi:CfdiRelacionados', {'TipoRelacion': relacion_tipo})
            for u in related_uuids:
                SubElement(rel, 'cfdi:CfdiRelacionado', {'UUID': u})

        # Método/forma (solo Ingreso/Egreso)
        if tipo in ('I', 'E'):
            if metodo:
                comprobante.set('MetodoPago', metodo)
            if forma:
                comprobante.set('FormaPago', forma)

            cs = SubElement(comprobante, 'cfdi:Conceptos')
            for it in conceptos_calc:
                nodo = SubElement(cs, 'cfdi:Concepto', {
                    'ClaveProdServ': it['clave_sat'],
                    'NoIdentificacion': it['no_ident'],
                    'Cantidad': f"{it['qty']:.2f}",
                    'ClaveUnidad': it['clave_unidad'],
                    'Descripcion': it['descripcion'],
                    'ValorUnitario': f"{it['vu']:.2f}",
                    'Importe': f"{it['base']:.2f}",      # <-- SIN impuestos (FIX #2)
                    'ObjetoImp': it['imp_obj'],
                })
                if it['imp_obj'] in ('02', '03') and it['traslados']:
                    imps = SubElement(nodo, 'cfdi:Impuestos')
                    tras = SubElement(imps, 'cfdi:Traslados')
                    for t in it['traslados']:
                        SubElement(tras, 'cfdi:Traslado', t)

            if traslados_total:
                SubElement(comprobante, 'cfdi:Impuestos', {
                    'TotalImpuestosTrasladados': f"{traslados_total:.2f}"
                })

            
            #_logger = logging.getLogger(__name__)
            _logger.info(f"=== CFDI fecha a usar: {fecha}============================================================================")
            _logger.info(f"=== RFC emisor: {emisor_rfc}====================================================================================")

            xml_bytes = tostring(comprobante, encoding='utf-8', xml_declaration=True)
            _logger.info("CFDI DEBUG | XML bytes len=%s head=%s", len(xml_bytes), xml_bytes[:120])

            _logger.info("CFDI DEBUG | EMISOR RFC=%s | company_id=%s", emisor_rfc, self.env.company.id)
            _logger.info("CFDI DEBUG | FECHA_XML=%s | NOW_UTC=%s | USER_TZ=%s", fecha, fields.Datetime.now(), self.env.user.tz or 'America/Mexico_City')
            _logger.info("CFDI DEBUG | XML bytes len=%s head=%s", len(xml_bytes), xml_bytes[:120])
            #self._log_csd_validity()
            #stamped = provider._stamp_xml(xml)

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
        b64 = base64.b64encode(xml_bytes).decode("ascii")
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
    
    # ---------- Utils de fecha y CSD ----------
    def _mx_local_now(self):
        tz = self.env.user.tz or 'America/Mexico_City'
        return fields.Datetime.context_timestamp(self.with_context(tz=tz), fields.Datetime.now())

    def _as_cfdi_fecha(self, dt):
        # antiskew: -120s para evitar “futuro” vs PAC
        return (dt - timedelta(seconds=120)).strftime('%Y-%m-%dT%H:%M:%S')

    def _debug_dates(self, fecha_str, cpostal):
        now_utc = fields.Datetime.now()
        local_now = self._mx_local_now()
        _logger.info("CFDI DEBUG | NOW_UTC=%s | NOW_LOCAL=%s | USER_TZ=%s | FECHA_XML=%s | CP=%s",
                     now_utc, local_now, self.env.user.tz or 'America/Mexico_City', fecha_str, cpostal)
        try:
            dt_xml = fields.Datetime.from_string(fecha_str.replace('T', ' '))
            delta = abs(now_utc - dt_xml)
            _logger.info("CFDI DEBUG | delta(now_utc vs FECHA_XML)=%s", delta)
        except Exception as e:
            _logger.warning("CFDI DEBUG | No se pudo evaluar delta: %s", e)

    def _company_cer_pem(self):
        c = self.env.company
        # 1) Si ya tienes PEM en texto:
        txt = getattr(c, 'cfdi_sw_cer_pem', '') or ''
        if txt.strip().startswith('-----BEGIN CERTIFICATE-----'):
            return txt.strip()
        # 2) Si tienes archivo (binario base64 del .cer DER):
        data = getattr(c, 'cfdi_sw_cer_file', False)
        if data:
            
            der = base64.b64decode(data)
            try:
                from cryptography import x509
                from cryptography.hazmat.primitives.serialization import Encoding
                cert = x509.load_der_x509_certificate(der)
                return cert.public_bytes(Encoding.PEM).decode('utf-8')
            except Exception:
                pass
        return ''

    def _log_csd_validity(self):
        pem = self._company_cer_pem()
        if not pem:
            _logger.warning("CSD DEBUG | No tengo PEM del CSD; no puedo leer vigencia.")
            return
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            cert = x509.load_pem_x509_certificate(pem.encode('utf-8'), default_backend())
            _logger.info("CSD DEBUG | notBefore(UTC)=%s | notAfter(UTC)=%s | serial=%s",
                         cert.not_valid_before, cert.not_valid_after, cert.serial_number)
        except Exception as e:
            _logger.warning("CSD DEBUG | No se pudo leer vigencia del CSD: %s", e)

    def _is_305(self, payload=None, exc=None):
        """Detecta '305 - La fecha de emisión no está dentro de la vigencia del CSD' en payload/exception."""
        txt = ""
        if isinstance(payload, dict):
            txt = " ".join(str(payload.get(k, "")) for k in ("code", "message", "mensaje", "error", "detail", "Message"))
        if exc:
            txt += " " + str(exc)
        txt_low = txt.lower()
        return "305" in txt_low or "vigencia del csd" in txt_low