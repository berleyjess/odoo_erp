#mx_cfdi_provider_sw/models/provider_sw.py
# -*- coding: utf-8 -*-
import base64
import json
from odoo import models, api, _
from odoo.exceptions import UserError
import time
import logging

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


class CfdiProviderSW(models.AbstractModel):
    _name = "mx.cfdi.engine.provider.sw"
    _inherit = "mx.cfdi.engine.provider.base"
    _description = "CFDI Provider - SW Sapien"

 #==================== Configuración =====================#
    def _cfg(self):
        ICP = self.env['ir.config_parameter'].sudo()
        c = self.env.company

        sandbox  = c.cfdi_sw_sandbox if c.cfdi_sw_sandbox is not None \
                   else (ICP.get_param('mx_cfdi_sw.sandbox', '1') in ('1','True','true'))
        base_url = (c.cfdi_sw_base_url or ICP.get_param('mx_cfdi_sw.base_url')
                    or ('https://services.sw.com.mx' if not sandbox else 'https://services.test.sw.com.mx'))

        # NUEVO: base de API (datawarehouse)
        api_base = 'https://api.sw.com.mx' if not sandbox else 'https://api.test.sw.com.mx'
        # Toma los binarios ya en b64 (Binary fields) — si son bytes, pásalos a str
        def _as_str(v):
            return v.decode('ascii') if isinstance(v, (bytes, bytearray)) else (v or '')

        return {
            'sandbox': sandbox,
            'base_url': base_url.rstrip('/'),
            'api_base_url': api_base,
            'token':        c.cfdi_sw_token        or ICP.get_param('mx_cfdi_sw.token') or '',
            'user':         c.cfdi_sw_user         or ICP.get_param('mx_cfdi_sw.user') or '',
            'password':     c.cfdi_sw_password     or ICP.get_param('mx_cfdi_sw.password') or '',
            'rfc':         (c.cfdi_sw_rfc or c.vat or ICP.get_param('mx_cfdi_sw.rfc') or '').upper(),
            'cer_b64':      _as_str(c.cfdi_sw_cer_file),
            'key_b64':      _as_str(c.cfdi_sw_key_file),
            'key_password': c.cfdi_sw_key_password or ICP.get_param('mx_cfdi_sw.key_password') or '',
        }
    #==================== Métodos de utilidad =====================#

    # --- NUEVO: consulta datawarehouse por UUID y descarga XML/acuse ---
    def _dw_lookup(self, uuid):
        """Devuelve el objeto del DW para ese UUID o None si aún no aparece."""
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg()
        url = f"{cfg['api_base_url'].rstrip('/')}/datawarehouse/v1/live/{uuid}"
        r = requests.get(url, headers=self._headers(cfg), timeout=30)
        if r.status_code >= 400:
            return None
        try:
            js = r.json()
        except Exception:
            return None

        # Forma oficial: data.records[] (ver documentación)
        data = js.get('data') if isinstance(js, dict) else None
        recs = (data or {}).get('records') if isinstance(data, dict) else None

        # Fallbacks por si cambian nombres clave
        if not isinstance(recs, list):
            for k in ('records', 'items', 'Data'):
                v = js.get(k) if isinstance(js, dict) else None
                if isinstance(v, list):
                    recs = v
                    break

        if isinstance(recs, list) and recs:
            return recs[0]
        return None

    def download_xml_by_uuid(self, uuid, tries=30, delay=1.0):
        """Devuelve {'xml': bytes, 'acuse': bytes|None} desde SW DW."""
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        start = time.monotonic()
        for attempt in range(max(1, int(tries))):   # ← no pises _
            rec = self._dw_lookup(uuid)
            if rec and rec.get('urlXml'):
                xml = requests.get(rec['urlXml'], timeout=60).content
                ack = None
                if rec.get('urlAckCfdi'):
                    try:
                        ack = requests.get(rec['urlAckCfdi'], timeout=60).content
                    except Exception:
                        ack = None
                return {'xml': xml, 'acuse': ack}
            time.sleep(max(0.1, float(delay)))

        waited = time.monotonic() - start
        # usa _() correctamente con % dict (y sin pisarlo en este scope)
        raise UserError(
            _("SW aún no expone el XML del UUID %(uuid)s (esperé %(sec).1f s). "
              "Inténtalo de nuevo en unos segundos.") % {'uuid': uuid, 'sec': waited}
        )
    
    def _upload_cert_from_company(self):
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg()
        cer_b64 = cfg.get('cer_b64') or ''
        key_b64 = cfg.get('key_b64') or ''
        pwd     = cfg.get('key_password') or ''
        if not (cer_b64 and key_b64 and pwd):
            raise UserError(_('Falta CSD en Ajustes (CER/KEY/Password).'))

        url = cfg['base_url'] + '/certificates/save'
        payload = {
            "type": "stamp",
            "b64Cer": cer_b64,  # ya está en base64
            "b64Key": key_b64,  # ya está en base64
            "password": pwd,
        }
        r = requests.post(url, headers=self._headers(cfg, json_ct=True),
                          data=json.dumps(payload), timeout=60)
        if r.status_code >= 400:
            try:
                data = r.json(); msg = data.get('message') or data.get('Message') or r.text
            except Exception:
                msg = r.text
            raise UserError(_('SW: error al cargar CSD: %s') % msg)
        return True
    
    #==================== Métodos de la API SW =====================#


    def _headers(self, cfg, *, json_ct=False):
        # No fijes Content-Type salvo que sea JSON; para multipart lo define requests.
        h = {}
        if json_ct:
            h['Content-Type'] = 'application/json'
        if cfg.get('token'):
            h['Authorization'] = f"Bearer {cfg['token']}"
        return h

    @api.model
    def _ping(self):
        """Verifica conectividad con SW.
        No existe /ping público; probamos la raíz y consideramos OK cualquier
        status <500 (incluye 200/401/403/404 según el edge/API gateway)."""
        if not requests:
            return False, 'Python package requests no disponible'
        cfg = self._cfg()
        url = cfg['base_url'].rstrip('/') + '/'  # probar raíz
        try:
            r = requests.get(url, headers=self._headers(cfg), timeout=10)
            code = r.status_code
            # Host accesible aunque la ruta raíz no tenga recurso
            if code < 500:
                # mensaje uniforme para el botón "Probar conexión"
                if code == 404:
                    return True, f'Host accesible, endpoint no disponible ({url}) [{code}]'
                return True, f'Conexión OK ({url}) [{code}]'
            return False, f'Respuesta {code}: {r.text[:200]}'
        except Exception as e:
            return False, f'Error de conexión: {e}'

    @api.model
    def _stamp_xml(self, xml_bytes):
        """Timbrado por emisión (multipart), según docs SW:
        POST {base}/cfdi33/issue/v4  con archivo XML."""
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode('utf-8')

        cfg = self._cfg()
        url = cfg['base_url'] + '/cfdi33/issue/v4'  # timbrado XML (multipart)
        files = {'xml': ('cfdi.xml', xml_bytes, 'application/xml')}
        resp = requests.post(url, headers=self._headers(cfg), files=files, timeout=60)
        
        if resp.status_code >= 400:
            # muestra el mensaje real de SW para depurar
            try:
                err = resp.json()
                msg = err.get('message') or err.get('Message') or resp.text
            except Exception:
                msg = resp.text
            raise UserError(_('Error timbrando con SW: %s') % msg)

        data = resp.json() if 'json' in resp.headers.get('Content-Type','') else {}
        uuid = (data.get('data') or {}).get('uuid') or data.get('uuid') or ''
        b64  = (data.get('data') or {}).get('cfdi') or data.get('cfdi') or data.get('Cfdi')

        if not (uuid and b64):
            raise UserError(_('SW no devolvió UUID/XML timbrado. Respuesta: %s') % (resp.text[:400],))

        xml_timbrado = base64.b64decode(b64)
        return {'uuid': uuid, 'xml_timbrado': xml_timbrado}


    def _cancel(self, uuid, rfc=None, cer_pem=None, key_pem=None, password=None,
                motivo='02', folio_sustitucion=None):
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg()
        rfc = (rfc or cfg.get('rfc') or '').upper()
        url = cfg['base_url'] + '/cfdi33/cancel/csd'
        payload = {
            'rfc': rfc,
            'b64Cer': cfg.get('cer_b64') or '',
            'b64Key': cfg.get('key_b64') or '',
            'password': password or cfg.get('key_password') or '',
            'uuid': uuid,
            'motivo': motivo,
            'folioSustitucion': folio_sustitucion or ''
        }
        r = requests.post(url, headers=self._headers(cfg, json_ct=True),
                          data=json.dumps(payload), timeout=60)
        if r.status_code >= 400:
            try:
                data = r.json(); msg = data.get('message') or data.get('Message') or r.text
            except Exception:
                msg = r.text
            raise UserError(_('Error al cancelar con SW: %s') % msg)

        data = r.json() if r.headers.get('Content-Type','').startswith('application/json') else {}
        acuse_b64 = data.get('acuse') or data.get('Acuse') or None
        acuse = base64.b64decode(acuse_b64) if acuse_b64 else None
        return {'status': data.get('status') or data.get('Status'), 'acuse': acuse}

    def _upload_cert_from_config(self):
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg()
        cer_pem = cfg.get('cer_pem') or ''
        key_pem = cfg.get('key_pem') or ''
        pwd = cfg.get('key_password') or ''
        if not (cer_pem and key_pem and pwd):
            raise UserError(_('Falta CSD en Ajustes (CER/KEY/Password).'))
    
        url = cfg['base_url'] + '/certificates/save'
        payload = {
            "type": "stamp",
            "b64Cer": base64.b64encode(cer_pem.encode('utf-8')).decode('ascii'),
            "b64Key": base64.b64encode(key_pem.encode('utf-8')).decode('ascii'),
            "password": pwd,
        }
        r = requests.post(url, headers=self._headers(cfg, json_ct=True), data=json.dumps(payload), timeout=60)
        if r.status_code >= 400:
            try:
                data = r.json(); msg = data.get('message') or data.get('Message') or r.text
            except Exception:
                msg = r.text
            raise UserError(_('SW: error al cargar CSD: %s') % msg)
        return True
    
    def _has_cert(self, rfc=None):
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg()
        url = cfg['base_url'] + '/certificates'
        resp = requests.get(url, headers=self._headers(cfg), timeout=30)

        # Parse robusto: puede venir JSON con content-type no-JSON, un dict con 'data',
        # una lista directa o incluso un string JSON.
        try:
            data = resp.json()
        except Exception:
            txt = resp.text or ''
            try:
                import json as _json
                data = _json.loads(txt) if txt else []
            except Exception:
                data = []

        # Normaliza a lista
        if isinstance(data, dict):
            for k in ('data', 'Data', 'items', 'certificates', 'Certificates', 'result', 'results'):
                v = data.get(k)
                if isinstance(v, list):
                    data = v
                    break
            else:
                data = [data]  # caso objeto único
        elif isinstance(data, str):
            try:
                import json as _json
                data = _json.loads(data)
            except Exception:
                data = []

        if not isinstance(data, list):
            data = []

        # Extrae RFC del certificado sin romper si cambian las llaves
        def _issuer_rfc(obj):
            return (obj.get('issuer_rfc') or obj.get('issuerRfc') or
                    obj.get('rfc') or obj.get('RFC') or '').upper() if isinstance(obj, dict) else ''

        rfc = (rfc or cfg.get('rfc') or '').upper()
        return any(_issuer_rfc(c) == rfc for c in data)

    def _debug_cfg(self):
        cfg = self._cfg()
        safe = {
            'sandbox': cfg.get('sandbox'),
            'base_url': cfg.get('base_url'),
            'rfc': cfg.get('rfc'),
            'token_present': bool(cfg.get('token')),
            'cer_b64_len': len(cfg.get('cer_b64') or ''),
            'key_b64_len': len(cfg.get('key_b64') or ''),
            'has_pwd': bool(cfg.get('key_password')),
        }
        _logger.info("SW DEBUG CFG: %s", safe)
        return safe

    def debug_list_certificates(self):
        """Listar lo que SW dice tener cargado y loggear vigencias si las expone."""
        if not requests:
            return False
        cfg = self._cfg()
        url = cfg['base_url'] + '/certificates'
        r = requests.get(url, headers=self._headers(cfg), timeout=30)
        try:
            data = r.json()
        except Exception:
            try:
                import json as _json
                data = _json.loads(r.text or '[]')
            except Exception:
                data = []
        if isinstance(data, dict):
            for k in ('data','items','results','certificates'):
                if isinstance(data.get(k), list):
                    data = data[k]
                    break
        if not isinstance(data, list):
            data = [data]
        # Logguea por RFC
        for i, c in enumerate(data):
            rfc  = (c.get('issuer_rfc') or c.get('issuerRfc') or c.get('rfc') or '').upper()
            # Algunos PAC exponen notBefore/notAfter/validFrom/validTo
            vfrom = c.get('valid_from') or c.get('not_before') or c.get('validFrom')
            vto   = c.get('valid_to')   or c.get('not_after')  or c.get('validTo')
            _logger.info("SW CERT[%s]: RFC=%s valid_from=%s valid_to=%s raw=%s", i, rfc, vfrom, vto, c)
        return True