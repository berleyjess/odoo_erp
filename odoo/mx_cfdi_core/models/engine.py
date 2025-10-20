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
register_namespace('pago20', 'http://www.sat.gob.mx/Pagos20')
import hashlib
import re, unicodedata


class CfdiEngine(models.AbstractModel):
    _name = "mx.cfdi.engine"
    _description = "CFDI Engine (service)"

    """
    Orquesta el timbrado CFDI:
    1) Construye el XML con _build_xml().
    2) Obtiene el proveedor PAC con _get_provider() y loguea CSD.
    3) Intenta timbrar; si detecta “305 (vigencia CSD)” reintenta con fecha UTC.
    4) Si el PAC no regresa XML, lo descarga por UUID.
    5) Crea mx.cfdi.document y adjunta el XML al origen con _attach_xml().
    Parámetros clave (kwargs-only): origin_model, origin_id, empresa_id, tipo, receptor_id,
    uso_cfdi, metodo, forma, relacion_tipo, relacion_moves, conceptos, moneda, serie, folio,
    fecha, extras.
    Retorna: dict {'uuid', 'attachment_id', 'document_id'}.
    Efectos colaterales: crea/adjunta ir.attachment y mx.cfdi.document; escribe logs.
    Lanza: UserError si falta empresa_id o si el PAC no devuelve UUID.
    """

    def generate_and_stamp(self, *, origin_model, origin_id, empresa_id=None, tipo, receptor_id,
                       uso_cfdi=None, metodo=None, forma=None,
                       relacion_tipo=None, relacion_moves=None,
                       conceptos=None, moneda="MXN", serie=None, folio=None,
                       fecha=None, extras=None):
        if not empresa_id:
            empresa_id = self.env.context.get('empresa_id')
        if not empresa_id:
            raise UserError(_('Se requiere empresa_id para timbrar'))
        
        # Asegurar que el contexto tenga empresa_id
        self = self.with_context(empresa_id=empresa_id)
        # 1) Construir XML
        xml = self._build_xml(
            tipo=tipo, receptor_id=receptor_id, conceptos=conceptos,
            uso_cfdi=uso_cfdi, metodo=metodo, forma=forma,
            relacion_tipo=relacion_tipo, relacion_moves=relacion_moves,
            moneda=moneda, serie=serie, folio=folio, fecha=fecha,
            extras=extras
        )

        # 2) Obtener provider y loggear cfg/vigencia CSD
        provider = self._get_provider()
        try:
            provider._debug_cfg()
            self._log_csd_validity()
        except Exception as e:
            _logger.warning("CFDI DEBUG | No se pudo loggear cfg/vigencia CSD: %s", e)

        # 3) Timbrar (con retry 305)
        stamped, saw_305 = None, False
        try:
            #==============================Log cfdi 4.0==============================
            try:
                txt = xml.decode("utf-8", errors="ignore") if isinstance(xml, (bytes, bytearray)) else str(xml)
                max_bytes = 8192  # 8 KB de preview; ajusta a tu gusto
                head = txt[:max_bytes]
                tail_note = f"\n...[truncated {len(txt) - max_bytes} bytes]" if len(txt) > max_bytes else ""
                _logger.info(
                    "CFDI OUT | PRE-STAMP XML | len=%s | sha256=%s\n%s%s",
                    len(xml),
                    hashlib.sha256(xml if isinstance(xml, (bytes, bytearray)) else txt.encode("utf-8")).hexdigest(),
                    head,
                    tail_note,
                )
            except Exception as e:
                _logger.warning("CFDI OUT | No se pudo loggear preview del XML: %s", e)

            try:
                cfg = provider._debug_cfg()  # ya loggea sandbox/base/rfc/token_fp
                # Verifica que el PAC ve el CSD del RFC activo
                has = provider._has_cert()
                _logger.warning("CFDI DEBUG | _has_cert(rfc=%s) -> %s", cfg.get('rfc'), has)
            except Exception as e:
                _logger.warning("CFDI DEBUG | provider precheck failed: %s", e)

            #=============================FIN Log cfdi 4.0=============================
            stamped = provider._stamp_xml(xml)
        except Exception as e:
            try:
                self._attach_prestamp(origin_model, origin_id, xml, note="error-pre-stamp")
            except Exception:
                pass
            if self._is_305(exc=e):
                saw_305 = True
            else:
                raise

        if saw_305 or self._is_305(payload=stamped):
            fecha_utc = fields.Datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            xml = self._build_xml(
                tipo=tipo, receptor_id=receptor_id, conceptos=conceptos,
                uso_cfdi=uso_cfdi, metodo=metodo, forma=forma,
                relacion_tipo=relacion_tipo, relacion_moves=relacion_moves,
                moneda=moneda, serie=serie, folio=folio, fecha=fecha_utc,
                extras=extras
            )
            stamped = provider._stamp_xml(xml)

        if not stamped or not stamped.get("uuid"):
            try:
                self._attach_prestamp(origin_model, origin_id, xml, note="no-uuid-pre-stamp")
            except Exception:
                pass
            raise UserError(_("El PAC no devolvió un UUID."))

        # 4) Descargar XML por UUID si no vino en respuesta
        if not stamped.get("xml_timbrado"):
            try:
                dl = provider.download_xml_by_uuid(stamped['uuid'], tries=10, delay=1.0)
                stamped['xml_timbrado'] = dl.get('xml')
                if dl.get('acuse'):
                    self.env['ir.attachment'].sudo().create({
                        'name': f"acuse-{stamped['uuid']}.xml",
                        'res_model': origin_model,
                        'res_id': origin_id,
                        'type': 'binary',
                        'datas': base64.b64encode(dl['acuse']).decode('ascii'),
                        'mimetype': 'application/xml',
                        'description': _('Acuse CFDI %s (SW DW)') % (stamped['uuid'],),
                    })
                    
            except Exception as e:
                _logger.info("CFDI DEBUG | provider returned keys=%s", list(stamped.keys()))

        # 5) Guardar y log extra (TFD)
        xml_bytes = stamped.get("xml_timbrado")
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode("utf-8")
        self._debug_dump_xml(xml_bytes, label="TIMBRADO XML",
                             param_key="mx_cfdi_core.log_xml_timbrado_full", limit_kb=256)

        try:
            import xml.etree.ElementTree as ET
            ns_cfdi = "http://www.sat.gob.mx/cfd/4"
            ns_tfd = "http://www.sat.gob.mx/TimbreFiscalDigital"
            root = ET.fromstring(xml_bytes)
            tfd = None
            for comp in root.findall(f".//{{{ns_cfdi}}}Complemento"):
                tfd = comp.find(f".//{{{ns_tfd}}}TimbreFiscalDigital")
                if tfd is not None:
                    break
            if tfd is not None:
                attrs = dict(tfd.attrib)
            else:
                _logger.info("CFDI DEBUG | TFD no encontrado en XML timbrado.")
        except Exception as e:
            _logger.warning("CFDI DEBUG | Error leyendo TFD: %s", e)
        
        xml_b64 = base64.b64encode(xml_bytes).decode("ascii")
        doc = self.env["mx.cfdi.document"].create({
            "empresa_id": empresa_id,
            "origin_model": origin_model,
            "origin_id": origin_id,
            "tipo": tipo,
            "uuid": stamped["uuid"],
            "xml": xml_b64,
            "state": "stamped",
        })

        att = self._attach_xml(origin_model, origin_id, stamped.get("xml_timbrado"), doc)
        return {"uuid": doc.uuid, "attachment_id": att.id, "document_id": doc.id}


    """
    Arma el <cfdi:Comprobante Version="4.0"> completo listo para timbrar:
        - Emisor desde empresas.empresa (RFC, Régimen, CP/LugarExpedicion, Nombre normalizado).
        - Receptor (RFC genérico o específico; valida Régimen y C.P. 5 dígitos).
        - Conceptos con claves SAT, unidad, cantidades, importes e impuestos por concepto.
        - Impuestos globales agregados por (Impuesto, TipoFactor, TasaOCuota).
        - Relaciones CFDI y/o InformacionGlobal (si viene en extras).
        - TipoCambio cuando la moneda != MXN.
    Parámetros: acepta kwargs (tipo, receptor_id, conceptos, uso_cfdi, metodo, forma,
    moneda, fecha, relacion_tipo, relacion_moves, related_uuids, extras, serie, folio, empresa_id).
    Retorna: bytes (XML UTF-8 con declaración).
    Lanza: UserError ante datos faltantes/incorrectos (empresa_id, RFC/Regímenes, CP, claves SAT, etc.).
    """

    @api.model
    def _build_xml(self, **kw):
        """
        - Receptor una sola vez.
        - Importes por concepto sin impuestos (Importe = Cantidad x ValorUnitario).
        - Agrega cfdi:Impuestos global con cfdi:Traslados agregados por (Impuesto, TipoFactor, TasaOCuota).
        - Valida CP del receptor (no '00000' si no es RFC genérico).
        """
        def fmt2(x):  return f"{float(x):.2f}"
        def fmt6(x):  return f"{float(x):.6f}"

        tipo         = kw.get('tipo') or 'I'
        receptor_id  = kw.get('receptor_id')
        conceptos_in = kw.get('conceptos') or []
        uso_default  = (kw.get('uso_cfdi') or '').strip() 
        metodo       = (kw.get('metodo') or '').strip() or None
        forma        = (kw.get('forma') or '').strip() or None
        moneda       = kw.get('moneda') or 'MXN'
        fecha        = (str(kw['fecha']).strip().replace(' ', 'T')[:19]
                        if kw.get('fecha') else self._as_cfdi_fecha(self._mx_local_now()))
        relacion_tipo    = kw.get('relacion_tipo') or None
        relacion_moves   = kw.get('relacion_moves') or None
        related_uuids_kw = kw.get('related_uuids') or []
        extras           = kw.get('extras') or {}
        serie            = (kw.get('serie') or '').strip() or None
        folio            = (kw.get('folio') or '').strip() or None


        empresa_id = self.env.context.get('empresa_id') or kw.get('empresa_id')
        if not empresa_id:
            raise UserError(_('Se requiere empresa_id para generar CFDI'))

        empresa = self.env['empresas.empresa'].browse(empresa_id)
        if not empresa.exists():
            raise UserError(_('Empresa no encontrada'))

        # Usar datos directamente de empresa
        cpostal = (empresa.cp or '').strip()
        if not (cpostal.isdigit() and len(cpostal) == 5):
            raise UserError(_("Configura el C.P. de la compañía (5 dígitos) para LugarExpedicion."))

        self._debug_dates(fecha, cpostal)

        emisor_rfc = (empresa.rfc or '').upper()
        if not emisor_rfc:
            raise UserError(_("Configura el RFC Emisor (cfdi_sw_rfc o VAT)."))

        is_moral = self._is_moral_rfc(emisor_rfc)
        reg_cfg = (empresa.regimen_fiscal or '').strip()
        if not reg_cfg:
            raise UserError(_("Falta el Régimen Fiscal de la empresa emisora."))
        _logger.info("CFDI EMISOR | regimen_efectivo=%s (fuente=empresas.empresa)", reg_cfg)


        PM_CODES = {'601','603','620','623','624','628'}
        PF_CODES = {'605','606','607','608','611','612','614','615','616'}
        if is_moral and reg_cfg in PF_CODES:
            raise UserError(_("El RFC %(rfc)s es de Persona Moral pero el régimen %(reg)s es de PF.") % {'rfc': emisor_rfc, 'reg': reg_cfg})
        if (not is_moral) and reg_cfg in PM_CODES:
            raise UserError(_("El RFC %(rfc)s es de Persona Física pero el régimen %(reg)s es de PM.") % {'rfc': emisor_rfc, 'reg': reg_cfg})

        emisor_regimen = reg_cfg
        emisor_nombre = (empresa.razonsocial or '').strip()
        if not emisor_nombre:
            raise UserError(_("Configura el nombre/razón social del emisor."))
        emisor_nombre = ' '.join(emisor_nombre.split()).upper()

        # Si es pago y no vino uso_cfdi, usar CP01 automáticamente
        if tipo == 'P' and not uso_default:
            uso_default = 'CP01'

        # Solo exigir UsoCFDI para I/E
        if tipo in ('I', 'E') and not uso_default:
            raise UserError(_("Debes indicar el UsoCFDI del receptor."))



        # ---- Precalcular conceptos + impuestos ----
        subtotal_sum = 0.0
        traslados_total = 0.0
        retenciones_total = 0.0

        is_pago = (tipo == 'P')
        subtotal_attr = '0' if is_pago else fmt2(subtotal_sum)
        total_attr = '0' if is_pago else fmt2(round(subtotal_sum + traslados_total - retenciones_total, 2))


        # Acumuladores para nivel Comprobante: (impuesto, tipo_factor, tasa_str) -> importe_total
        agg_tras = {}
        agg_base = {}
        agg_ret  = {}
        exentos_impuestos = set()
        exento_bases = {}

        conceptos_calc = []
        for c in conceptos_in:
            qty = float(c.get('cantidad') or c.get('qty') or 1.0)
            vu  = float(c.get('valor_unitario') or c.get('price') or 0.0)
            base = round(qty * vu, 2)
            subtotal_sum += base

            iva_ratio  = float(c.get('iva') or 0.0)     # 0.16, 0.08, 0.00
            ieps_ratio = float(c.get('ieps') or 0.0)
            iva_factor = (c.get('iva_factor') or '').title()  # 'Tasa' | 'Exento' (opcional)

            # Si trae estructura completa de impuestos, respétala; si no, calcula por ratio
            imp_obj = (c.get('objeto_imp') or
                       ('02' if (c.get('impuestos') or iva_ratio or ieps_ratio) else '01'))

            traslados = []
            if imp_obj == '02':
                if c.get('impuestos') and isinstance(c['impuestos'], dict):
                    for t in (c['impuestos'].get('traslados') or []):
                        t_base   = float(t.get('base', base) or base)
                        t_imp    = float(t.get('importe') or 0.0)
                        t_code   = str(t.get('impuesto') or '')
                        t_factor = str(t.get('tipo_factor') or 'Tasa')
                        t_tasa   = t.get('tasa_cuota')
                        if t_code in ('002','003'):
                            tasa_str = ''
                            if t_factor == 'Tasa' and t_tasa is not None:
                                tasa_str = fmt6(float(t_tasa))
                                agg_base[(t_code, 'Tasa', tasa_str)] = agg_base.get((t_code, 'Tasa', tasa_str), 0.0) + t_base
                                agg_tras[(t_code, 'Tasa', tasa_str)] = agg_tras.get((t_code, 'Tasa', tasa_str), 0.0) + t_imp
                                traslados_total += t_imp
                            elif t_factor == 'Exento':
                                exentos_impuestos.add(t_code)
                                exento_bases[t_code] = exento_bases.get(t_code, 0.0) + t_base
                            traslados.append({
                                'Base': fmt2(t_base), 'Impuesto': t_code, 'TipoFactor': t_factor,
                                **({'TasaOCuota': tasa_str} if tasa_str else {}),
                                **({'Importe': fmt2(t_imp)} if t_factor == 'Tasa' else {}),
                            })
                else:
                    if iva_ratio:
                        iva_imp = round(base * iva_ratio, 2)
                        tasa_str = fmt6(iva_ratio)
                        agg_base[('002','Tasa',tasa_str)] = agg_base.get(('002','Tasa',tasa_str), 0.0) + base
                        agg_tras[('002','Tasa',tasa_str)] = agg_tras.get(('002','Tasa',tasa_str), 0.0) + iva_imp
                        traslados_total += iva_imp  # ← AGREGAR ESTA LÍNEA
                        traslados.append({'Base': fmt2(base), 'Impuesto': '002', 'TipoFactor': 'Tasa',
                                          'TasaOCuota': tasa_str, 'Importe': fmt2(iva_imp)})
                    elif iva_factor == 'Tasa':
                        tasa_str = fmt6(0)
                        agg_base[('002','Tasa',tasa_str)] = agg_base.get(('002','Tasa',tasa_str), 0.0) + base
                        traslados.append({'Base': fmt2(base), 'Impuesto': '002', 'TipoFactor': 'Tasa',
                                          'TasaOCuota': tasa_str, 'Importe': fmt2(0)})
                    elif iva_factor == 'Exento':
                        exentos_impuestos.add('002')
                        exento_bases['002'] = exento_bases.get('002', 0.0) + base
                        traslados.append({'Base': fmt2(base), 'Impuesto': '002', 'TipoFactor': 'Exento'})
                
                    if ieps_ratio:
                        ieps_imp = round(base * ieps_ratio, 2)
                        tasa_str = fmt6(ieps_ratio)
                        agg_base[('003','Tasa',tasa_str)] = agg_base.get(('003','Tasa',tasa_str), 0.0) + base
                        agg_tras[('003','Tasa',tasa_str)] = agg_tras.get(('003','Tasa',tasa_str), 0.0) + ieps_imp
                        traslados_total += ieps_imp  # ← AGREGAR ESTA LÍNEA
                        traslados.append({'Base': fmt2(base), 'Impuesto': '003', 'TipoFactor': 'Tasa',
                                          'TasaOCuota': tasa_str, 'Importe': fmt2(ieps_imp)})

                # Si no quedó nada y era objeto de impuesto → márquese exento (con Base)
                if not traslados:
                    exentos_impuestos.add('002')
                    exento_bases['002'] = exento_bases.get('002', 0.0) + base
                    traslados.append({'Base': fmt2(base), 'Impuesto': '002', 'TipoFactor': 'Exento'})

            elif imp_obj == '03':
                traslados = []  # Objeto pero no obligado a desglose

            idx = len(conceptos_calc) + 1
            clave_sat = (c.get('clave_sat') or c.get('claveprodserv') or '').strip()
            if not clave_sat:
                raise UserError(_("Concepto #%s: falta ClaveProdServ (c_ClaveProdServ).") % idx)
            # formato típico de catálogo (8 dígitos). Si manejas excepciones, quita esta verificación.
            if not re.match(r'^\d{8}$', clave_sat):
                raise UserError(_("Concepto #%s: ClaveProdServ debe ser 8 dígitos (catálogo c_ClaveProdServ).") % idx)

            clave_unidad = (c.get('clave_unidad') or c.get('claveunidad') or '').strip()
            if not clave_unidad:
                raise UserError(_("Concepto #%s: falta ClaveUnidad (c_ClaveUnidad).") % idx)
            # validación básica de forma (2–5 alfanum). No es el catálogo completo.
            if not re.match(r'^[A-Z0-9]{2,5}$', clave_unidad):
                raise UserError(_("Concepto #%s: ClaveUnidad inválida (usa c_ClaveUnidad).") % idx)

            if ('valor_unitario' not in c and 'price' not in c):
                raise UserError(_("Concepto #%s: falta ValorUnitario.") % idx)

            if not (c.get('descripcion') or '').strip():
                raise UserError(_("Concepto #%s: falta Descripción.") % idx)

            conceptos_calc.append({
                'base': base,
                'imp_obj': imp_obj,
                'qty': qty,
                'vu': vu,
                'clave_sat': clave_sat,
                'no_ident': str(c.get('no_identificacion') or c.get('no_ident') or ''),
                'clave_unidad': clave_unidad,
                'descripcion': c.get('descripcion'),

                'traslados': traslados,
            })


        total_sum = round(subtotal_sum + traslados_total - retenciones_total, 2)

        # --- Comprobante ---
        exportacion = extras.get('exportacion') or '01'  # 01 = No aplica
        if tipo == 'P':
            # En CFDI de Pago el comprobante SIEMPRE es Moneda="XXX"
            moneda = 'XXX'
        comprobante = Element('cfdi:Comprobante', {
            'Version': '4.0',
            'Fecha': fecha,
            'Moneda': moneda,                     # ya forzas 'XXX' arriba si tipo == 'P'
            'TipoDeComprobante': {'I':'I','E':'E','P':'P'}.get(tipo, 'I'),
            'Exportacion': exportacion,
            'SubTotal': subtotal_attr,            # ← “0” en Pago
            'Total': total_attr,                  # ← “0” en Pago
            'LugarExpedicion': cpostal,
            'Sello': '',
            'Certificado': '',
            'NoCertificado': '',
            'xmlns:cfdi': 'http://www.sat.gob.mx/cfd/4',
            'xmlns:xsi':  'http://www.w3.org/2001/XMLSchema-instance',
            'xsi:schemaLocation': 'http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd',
        })


        # Si es CFDI de Pago, agrega el schemaLocation del complemento Pagos 2.0
        if tipo == 'P':
            sl = comprobante.get('xsi:schemaLocation', '').strip()
            pagos_pair = 'http://www.sat.gob.mx/Pagos20 http://www.sat.gob.mx/sitio_internet/cfd/Pagos/Pagos20.xsd'
            if pagos_pair not in sl:
                comprobante.set('xsi:schemaLocation', (sl + ' ' + pagos_pair).strip())

        ig = extras.get('informacion_global') if isinstance(extras, dict) else None
        if ig:
            SubElement(comprobante, 'cfdi:InformacionGlobal', {
                'Periodicidad': ig['periodicidad'],  # '01'..'06'
                'Meses': ig['meses'],                # '01'..'12'
                'A\u00f1o': ig['anio'],              # 'Año' con ñ
            })

        if serie:
            comprobante.set('Serie', serie)
        if folio:
            comprobante.set('Folio', folio)
        # TipoCambio si aplica
        # TipoCambio: solo para Ingreso/Egreso con moneda distinta a MXN (nunca para Pago/XXX)
        if tipo in ('I', 'E') and (moneda or 'MXN').upper() != 'MXN':
            tc = extras.get('tipo_cambio')
            if not tc:
                raise UserError(_("Para moneda distinta a MXN debes informar TipoCambio en extras['tipo_cambio']."))
            comprobante.set('TipoCambio', fmt6(tc))

        
        # Emisor
        emisor_nombre_raw = (empresa.razonsocial or '')
        if not emisor_nombre_raw.strip():
            raise UserError(_("Configura el nombre/razón social del emisor."))
        emisor_nombre = CfdiEngine._sat_norm_name(emisor_nombre_raw)

        
        SubElement(comprobante, 'cfdi:Emisor', {
            'Rfc': emisor_rfc,
            'Nombre': emisor_nombre,
            'RegimenFiscal': str(emisor_regimen),
        })

        # Receptor
        
        receptor = self.env['res.partner'].browse(receptor_id) if receptor_id else False
        rec_rfc = (getattr(receptor, 'vat', '') or '').strip().upper() or 'XAXX010101000'
        is_generic = rec_rfc in ('XAXX010101000', 'XEXX010101000')


        # --- Receptor (genérico) ---
        if is_generic:
            rec_regimen = '616'
            rec_nombre  = 'PUBLICO EN GENERAL'
            uso_cfdi_ok = (uso_default or '')
            if not uso_cfdi_ok:
                raise UserError(_("Para RFC genérico (%s) debes indicar UsoCFDI (sugerido 'S01').") % rec_rfc)

            rec_cp = '00000' if rec_rfc == 'XEXX010101000' else cpostal
        else:
            rec_nombre = self._sat_norm_name(self._legal_name(receptor, normalize=False))
            if not rec_nombre:
                raise UserError(_("Captura el nombre/razón social del receptor en el contacto."))

            rec_regimen = (
                getattr(receptor, 'l10n_mx_edi_fiscal_regime', None)
                or getattr(receptor, 'cfdi_regimen_fiscal', None)
            )
            if not rec_regimen:
                raise UserError(_("Captura el Régimen Fiscal del receptor (l10n_mx_edi_fiscal_regime/cfdi_regimen_fiscal)."))

            rec_cp = (getattr(receptor, 'zip', None)
                      or (getattr(receptor, 'parent_id', False) and receptor.parent_id.zip)
                      or '').strip()
            rec_cp = ''.join(ch for ch in (rec_cp or '') if ch.isdigit())
            if not (rec_cp.isdigit() and len(rec_cp) == 5):
                raise UserError(_("Captura el C.P. fiscal (5 dígitos) del receptor en el contacto."))


            # Usa el uso_cfdi que te pasaron (o G03 por default), NO 'S01'
            uso_cfdi_ok = uso_default
            if not uso_cfdi_ok:
                raise UserError(_("Debes indicar el UsoCFDI del receptor."))



        SubElement(comprobante, 'cfdi:Receptor', {
            'Rfc': rec_rfc,
            'Nombre': rec_nombre,
            'UsoCFDI': uso_cfdi_ok,
            'DomicilioFiscalReceptor': rec_cp,
            'RegimenFiscalReceptor': str(rec_regimen),
        })

        # Relaciones
        related_uuids = list(related_uuids_kw)
        if relacion_moves:
            for rm in relacion_moves:
                if getattr(rm, 'l10n_mx_edi_cfdi_uuid', False):
                    related_uuids.append(rm.l10n_mx_edi_cfdi_uuid)
        if relacion_tipo and related_uuids:
            rel = SubElement(comprobante, 'cfdi:CfdiRelacionados', {'TipoRelacion': relacion_tipo})
            for u in related_uuids:
                SubElement(rel, 'cfdi:CfdiRelacionado', {'UUID': u})

        # Método/forma (solo I/E)
        if tipo in ('I','E'):
            if not uso_cfdi_ok:
                raise UserError(_("Debes indicar el UsoCFDI del receptor."))
            if metodo == 'PUE' and (not forma or forma == '99'):
                raise UserError(_("Para PUE debes especificar una FormaPago distinta de '99'."))
            if metodo == 'PPD' and forma and forma != '99':
                raise UserError(_("Para PPD la FormaPago debe ser '99 - Por definir'."))

            if metodo:
                comprobante.set('MetodoPago', metodo)
            if forma:
                comprobante.set('FormaPago', forma)

            cs = SubElement(comprobante, 'cfdi:Conceptos')
            for it in conceptos_calc:
                
                attrs_concepto = {
                    'ClaveProdServ': it['clave_sat'],
                    'Cantidad': fmt6(it['qty']),
                    'ClaveUnidad': it['clave_unidad'],
                    'Descripcion': it['descripcion'],
                    'ValorUnitario': fmt6(it['vu']),
                    'Importe': fmt2(it['base']),
                    'ObjetoImp': it['imp_obj'],
                }
                if it.get('no_ident'):
                    attrs_concepto['NoIdentificacion'] = it['no_ident']
                nodo = SubElement(cs, 'cfdi:Concepto', attrs_concepto)

                if it['imp_obj'] in ('02','03') and it['traslados']:
                    imps = SubElement(nodo, 'cfdi:Impuestos')
                    tras = SubElement(imps, 'cfdi:Traslados')
                    for t in it['traslados']:
                        SubElement(tras, 'cfdi:Traslado', t)

            # ---- Impuestos globales (OBLIGATORIOS si hubo impuestos en conceptos) ----
            if agg_tras or agg_ret or exento_bases:
                attrs_imp = {}
                if traslados_total:
                    attrs_imp['TotalImpuestosTrasladados'] = fmt2(traslados_total)
                if retenciones_total:
                    attrs_imp['TotalImpuestosRetenidos'] = fmt2(retenciones_total)
                imp_glob = SubElement(comprobante, 'cfdi:Impuestos', attrs_imp)

                if agg_ret:
                    rets = SubElement(imp_glob, 'cfdi:Retenciones')
                    for (imp, _tf, _tasa), importe in sorted(agg_ret.items()):
                        SubElement(rets, 'cfdi:Retencion', {'Impuesto': imp, 'Importe': fmt2(importe)})

                tras = SubElement(imp_glob, 'cfdi:Traslados')
                for key, importe in sorted(agg_tras.items()):
                    imp, tf, tasa = key
                    SubElement(tras, 'cfdi:Traslado', {
                        'Impuesto': imp,
                        'TipoFactor': tf,
                        'TasaOCuota': tasa or fmt6(0),
                        'Base': fmt2(agg_base.get(key, 0.0)),  # <<< REQUERIDO EN CFDI 4.0
                        'Importe': fmt2(importe),
                    })

                # Si NO hubo traslados con Tasa y sí hubo EXENTOS, el SAT permite reportarlos con Base a nivel global
                if not agg_tras and exento_bases:
                    for imp, base_sum in sorted(exento_bases.items()):
                        SubElement(tras, 'cfdi:Traslado', {
                            'Impuesto': imp, 'TipoFactor': 'Exento', 'Base': fmt2(base_sum),
                        })
        # === Estructura para CFDI de Pago (tipo 'P') ===
        # === Estructura para CFDI de Pago (tipo 'P') ===
        if tipo == 'P':
            # Concepto obligatorio 84111506
            cs = SubElement(comprobante, 'cfdi:Conceptos')
            SubElement(cs, 'cfdi:Concepto', {
                'ClaveProdServ': '84111506',
                'Cantidad': '1',         # ← sin decimales
                'ClaveUnidad': 'ACT',
                'Descripcion': 'Pago',
                'ValorUnitario': '0',    # ← sin decimales (recomendado)
                'Importe': '0',          # ← sin decimales (recomendado)
                'ObjetoImp': '01',
            })


            # Complemento Pagos 2.0
            comp = SubElement(comprobante, 'cfdi:Complemento')
            pagos = SubElement(comp, '{http://www.sat.gob.mx/Pagos20}Pagos', {'Version': '2.0'})

            # --- PATCH (orden correcto): primero Totales, luego los Pagos ---
            pagos_list = list((extras.get('pagos') or []))
            total_montos = sum(float(p.get('monto', 0.0)) for p in pagos_list)

            # 1) Totales ANTES que Pago
            SubElement(pagos, '{http://www.sat.gob.mx/Pagos20}Totales', {
                'MontoTotalPagos': fmt2(total_montos),
                # Si algún día agregas traslados/retenciones en el pago, agrega aquí los atributos de totales:
                # 'TotalTrasladosBaseIVA16': fmt2(...),
                # 'TotalTrasladosImpuestoIVA16': fmt2(...),
                # etc.
            })

            # 2) Luego cada Pago y sus Doctos
            for p in pagos_list:
                monto = float(p.get('monto', 0.0))
                moneda_p = (p.get('moneda', 'MXN') or 'MXN').upper()

                attrs_pago = {
                    'FechaPago': p['fecha'],
                    'FormaDePagoP': p.get('forma', '03'),
                    'MonedaP': moneda_p,
                    'Monto': fmt2(monto),
                }

                # Requerimiento SAT/PAC:
                # - Si MonedaP = MXN => TipoCambioP = "1" (sin decimales)
                # - Si MonedaP ≠ MXN => TipoCambioP obligatorio con el TC real (hasta 6 decimales)
                if moneda_p == 'MXN':
                    attrs_pago['TipoCambioP'] = '1'
                else:
                    tc_p = p.get('tipo_cambio_p') or p.get('tipo_cambio') or p.get('tc')
                    if not tc_p:
                        raise UserError(_("Para MonedaP distinta de MXN debes informar TipoCambioP en el pago."))
                    attrs_pago['TipoCambioP'] = fmt6(tc_p)

                pago = SubElement(pagos, '{http://www.sat.gob.mx/Pagos20}Pago', attrs_pago)
                for d in (p.get('docs') or []):
                    attrs = {
                        'IdDocumento': d['uuid'],
                        'MonedaDR': p.get('moneda', 'MXN'),
                        'EquivalenciaDR': '1',
                        'NumParcialidad': str(d.get('num_parcialidad', 1)),
                        'ImpSaldoAnt': fmt2(d.get('saldo_anterior', 0)),
                        'ImpPagado': fmt2(d.get('importe_pagado', 0)),
                        'ImpSaldoInsoluto': fmt2(d.get('saldo_insoluto', 0)),
                        'ObjetoImpDR': '01',
                    }
                    if d.get('serie'):
                        attrs['Serie'] = d['serie']
                    if d.get('folio'):
                        attrs['Folio'] = d['folio']
                    SubElement(pago, '{http://www.sat.gob.mx/Pagos20}DoctoRelacionado', attrs)
            # --- /PATCH ---


        _logger.info("CFDI RECEPTOR | RFC=%s | NombreXML='%s' | Regimen=%s | CP=%s | UsoCFDI=%s",
             rec_rfc, rec_nombre, rec_regimen, rec_cp, uso_cfdi_ok)

        xml_bytes = tostring(comprobante, encoding='utf-8', xml_declaration=True)
        self._debug_dump_xml(xml_bytes, label="PRE-STAMP XML", param_key="mx_cfdi_core.log_xml_full", limit_kb=256)
        return xml_bytes

    # ======================== utils ================================
    # Devuelve la fecha/hora actual en la zona del usuario (por defecto America/Mexico_City) usando la API de Odoo (context_timestamp).
    def _mx_local_now(self):
        tz = self.env.user.tz or 'America/Mexico_City'
        return fields.Datetime.context_timestamp(self.with_context(tz=tz), fields.Datetime.now())

    # Convierte un datetime a string CFDI “YYYY-MM-DDTHH:MM:SS” aplicando antiskew (-120s) para evitar rechazos por “fecha en el futuro” del PAC.
    def _as_cfdi_fecha(self, dt):
        # antiskew: -120s para evitar “futuro” vs PAC
        return (dt - timedelta(seconds=120)).strftime('%Y-%m-%dT%H:%M:%S')

    # Obtiene el certificado CSD de la empresa en formato PEM:
        # - Usa texto PEM si está en empresas.empresa.cfdi_sw_cer_pem.
        # - Si hay archivo en binario (cfdi_sw_cer_file), intenta DER→PEM; si ya es PEM lo usa.
    # Retorna: str PEM o cadena vacía si no se pudo obtener.
    def _empresa_cer_pem(self):
        empresa_id = self.env.context.get('empresa_id')
        empresa = self.env['empresas.empresa'].browse(empresa_id)
        # 1) Si tuvieras PEM en texto (opcional):
        txt = getattr(empresa, 'cfdi_sw_cer_pem', '') or ''
        if isinstance(txt, str) and txt.strip().startswith('-----BEGIN CERTIFICATE-----'):
            return txt.strip()

        # 2) Si tienes archivo binario (.cer/.pem) en el campo Binary:
        data = getattr(empresa, 'cfdi_sw_cer_file', False)
        if data:
            try:
                from cryptography import x509
                from cryptography.hazmat.primitives.serialization import Encoding
                der_or_pem = base64.b64decode(data)
                # intenta DER→PEM; si ya es PEM, úsalo tal cual
                try:
                    cert = x509.load_der_x509_certificate(der_or_pem)
                    return cert.public_bytes(Encoding.PEM).decode('utf-8')
                except Exception:
                    pem_txt = der_or_pem.decode('utf-8', errors='ignore')
                    if 'BEGIN CERTIFICATE' in pem_txt:
                        return pem_txt
            except Exception:
                pass
        return ''
    
    # Resuelve y devuelve el proveedor de timbrado (modelo PAC) para la empresa en contexto.
    # Lee empresas.empresa.cfdi_provider o el parámetro del sistema 'mx_cfdi_engine.provider'.
    # Devuelve el record del proveedor con contexto empresa_id.
    # Lanza: UserError si falta empresa_id o si el modelo de proveedor es inválido.
    def _get_provider(self):
        empresa_id = self.env.context.get('empresa_id')
        if not empresa_id:
            raise UserError(_('Se requiere empresa_id en el contexto'))

        empresa = self.env['empresas.empresa'].browse(empresa_id)
        ICP = self.env['ir.config_parameter'].sudo()

        # 1) Valor elegido en Ajustes (res.config.settings) -> icp param
        provider_key = (ICP.get_param('mx_cfdi_engine.provider', '') or '').strip()
    
        # 2) (Opcional) Por empresa, si lo manejas
        #if not provider_key:
        #    provider_key = (getattr(empresa, 'cfdi_provider', '') or '').strip()
    #
        ## 3) Fallback
        if not provider_key:
            raise UserError(_('Se requiere que seleccione el proveedor de CFDI en Ajustes.'))
        #    provider_key = 'mx.cfdi.engine.provider.dummy'
    
        _logger.info(
            "CFDI PROVIDER | resolved=%s | empresa=%s | icp=%s",
            provider_key, getattr(empresa, 'cfdi_provider', None),
            ICP.get_param('mx_cfdi_engine.provider', '')
        )
    
        try:
            return self.env[provider_key].with_context(empresa_id=empresa_id)
        except KeyError:
            raise UserError(_("Proveedor CFDI inválido: %s") % provider_key)



    # Crea un ir.attachment (application/xml) con el CFDI timbrado y lo enlaza al documento de origen (origin_model, origin_id). Usa el UUID para nombrar el archivo.
    # Retorna: ir.attachment (record).
    # Lanza: UserError si no se recibió xml_bytes.
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
    
    # Adjunta el XML previo al timbrado (para auditoría/diagnóstico). No lanza error si falta xml_bytes; solo regresa.
    def _attach_prestamp(self, origin_model, origin_id, xml_bytes, note="pre-stamp"):
        if not xml_bytes:
            return
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode('utf-8')
        self.env['ir.attachment'].sudo().create({
            'name': f'{note}-{fields.Datetime.now()}.xml',
            'res_model': origin_model,
            'res_id': origin_id,
            'type': 'binary',
            'datas': base64.b64encode(xml_bytes).decode('ascii'),
            'mimetype': 'application/xml',
            'description': _('XML previo a timbrado (%s)') % note,
        })

    # Solicita la cancelación al PAC para un UUID de CFDI:
        # - Usa el proveedor correspondiente a la empresa en contexto.
        # - Marca el mx.cfdi.document como 'canceled' si existe.
        # - Adjunta el acuse (si el PAC lo regresa) al origen.
    # Parámetros (kwargs-only): origin_model, origin_id, uuid, motivo, folio_sustitucion.
    # Retorna: dict/respuesta del proveedor.
    # Lanza: UserError si faltan UUID o RFC emisor.
    @api.model
    def cancel_cfdi(self, *, origin_model, origin_id, uuid, motivo='02', folio_sustitucion=None):
        provider = self._get_provider()
        empresa_id = self.env.context.get('empresa_id')
        empresa = self.env['empresas.empresa'].browse(empresa_id)
        rfc = (empresa.rfc or '').upper()
        if not (uuid and rfc):
            raise UserError(_('Faltan parámetros para cancelar: uuid o RFC del emisor(empresa).'))

        # El proveedor SW ya lee CSD/KEY/Password desde empresas.empresa vía self._cfg()
        res = provider._cancel(uuid, rfc=rfc, motivo=motivo, folio_sustitucion=folio_sustitucion)

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
                'datas': base64.b64encode(acuse).decode('ascii'),
                'mimetype': 'application/xml',
                'description': _('Acuse de cancelación %s') % (uuid,),
            })
        return res
    
    # Obtiene el nombre legal de un partner (l10n_mx_edi_legal_name o name).
    # Si normalize=True, aplica normalización SAT con _sat_norm_name.
    # Retorna: str (puede ser vacío).
    @staticmethod
    def _legal_name(p, *, normalize=False):
        raw = (getattr(p, 'l10n_mx_edi_legal_name', None) or getattr(p, 'name', None) or '').strip()
        if not raw:
            return ''
        return CfdiEngine._sat_norm_name(raw) if normalize else raw

    # ======================= debugs/logs =======================
    
    # Loguea hash SHA256 y tamaño del XML y, opcionalmente, contenido completo/truncado.
    # Se controla con el parámetro del sistema 'param_key' ('1/true/yes' para habilitar).
    # No lanza; atrapa sus propias excepciones de logging.
    def _debug_dump_xml(self, xml_bytes, *, label="XML", param_key="mx_cfdi_core.log_xml_full", limit_kb=128):
        """Loggea el XML (completo o truncado) y su SHA256. Controlado por parámetro del sistema."""
        try:
            ICP = self.env['ir.config_parameter'].sudo()
            on = (ICP.get_param(param_key, '0') or '').lower() in ('1', 'true', 'yes')
            # Siempre loggeamos el hash para rastreo; el contenido solo si 'on'
            h = hashlib.sha256(xml_bytes if isinstance(xml_bytes, (bytes, bytearray)) else str(xml_bytes).encode('utf-8')).hexdigest()
            _logger.info("CFDI DEBUG | %s SHA256=%s | len=%s", label, h, len(xml_bytes or b""))
            if not on:
                return
            txt = xml_bytes.decode('utf-8', errors='ignore') if isinstance(xml_bytes, (bytes, bytearray)) else str(xml_bytes)
            max_bytes = limit_kb * 1024
            if len(txt) > max_bytes:
                _logger.info("CFDI DEBUG | %s (primeros %d KB):\n%s", label, limit_kb, txt[:max_bytes])
            else:
                _logger.info("CFDI DEBUG | %s FULL:\n%s", label, txt)
        except Exception as e:
            _logger.warning("CFDI DEBUG | Error en _debug_dump_xml(%s): %s", label, e)

    # Intenta leer el certificado CSD en PEM y cargarlo con cryptography.x509 para
    # validar que es legible (y dejar rastro en logs). No falla el flujo si no puede.
    def _log_csd_validity(self):
        pem = self._empresa_cer_pem()
        if not pem:
            _logger.warning("CSD DEBUG | No tengo PEM del CSD; no puedo leer vigencia.")
            return
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            cert = x509.load_pem_x509_certificate(pem.encode('utf-8'), default_backend())
        except Exception as e:
            _logger.warning("CSD DEBUG | No se pudo leer vigencia del CSD: %s", e)

    # Utilidad de diagnóstico: compara la FECHA del XML con now_utc y registra delta (comentado) para detectar desfases. No interrumpe el flujo.
    def _debug_dates(self, fecha_str, cpostal):
        now_utc = fields.Datetime.now()
        local_now = self._mx_local_now()
        try:
            dt_xml = fields.Datetime.from_string(fecha_str.replace('T', ' '))
            delta = abs(now_utc - dt_xml)
        #    _logger.info("CFDI DEBUG | delta(now_utc vs FECHA_XML)=%s", delta)
        except Exception as e:
            _logger.warning("CFDI DEBUG | No se pudo evaluar delta: %s", e)


    # =============================== Validaciones  ================================

    # Determina si un RFC es de Persona Moral (longitud 12, excluye RFC genéricos).
    # Retorna: bool.
    @staticmethod
    def _is_moral_rfc(rfc: str) -> bool:
        rfc = (rfc or '').strip().upper()
        if rfc in ('XAXX010101000', 'XEXX010101000'):
            return False
        return len(rfc) == 12
    
    # Normaliza una cadena a formato aceptado por SAT:
        # - Mayúsculas, sin acentos, solo [A-Z0-9 &], espacios colapsados.
    # Retorna: str.
    @staticmethod
    def _sat_norm_name(txt: str) -> str:
        t = (txt or '').strip().upper()
        t = ''.join(c for c in unicodedata.normalize('NFKD', t) if not unicodedata.combining(c))
        t = re.sub(r'[^A-Z0-9 &]', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t
    
    # Detecta el error SAT/PAC “305 – la fecha de emisión no está dentro de la vigencia del CSD” en un payload o excepción.
    # Retorna: bool (True si encuentra indicios del 305).
    def _is_305(self, payload=None, exc=None):
        """Detecta '305 - La fecha de emisión no está dentro de la vigencia del CSD' en payload/exception."""
        txt = ""
        if isinstance(payload, dict):
            txt = " ".join(str(payload.get(k, "")) for k in ("code", "message", "mensaje", "error", "detail", "Message"))
        if exc:
            txt += " " + str(exc)
        txt_low = txt.lower()
        return "305" in txt_low or "vigencia del csd" in txt_low

    # =============================== Fin Validaciones ================================