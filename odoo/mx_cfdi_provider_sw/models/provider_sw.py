#mx_cfdi_provider_sw/models/provider_sw.py
# -*- coding: utf-8 -*-
import base64
import json
from odoo import models, api, _
from odoo.exceptions import UserError

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


class CfdiProviderSW(models.AbstractModel):
    _name = "mx.cfdi.engine.provider.sw"
    _inherit = "mx.cfdi.engine.provider.base"
    _description = "CFDI Provider - SW Sapien"

    def _cfg(self):
        ICP = self.env['ir.config_parameter'].sudo()
        sandbox = ICP.get_param('mx_cfdi_sw.sandbox', '1') in ('1', 'True', 'true')
        base_url = (ICP.get_param('mx_cfdi_sw.base_url') or
                    ('https://services.sw.com.mx' if not sandbox else 'https://services.test.sw.com.mx'))
        token = ICP.get_param('mx_cfdi_sw.token') or ''
        user = ICP.get_param('mx_cfdi_sw.user') or ''
        password = ICP.get_param('mx_cfdi_sw.password') or ''
        rfc = ICP.get_param('mx_cfdi_sw.rfc') or (self.env.company.vat or '')
        cer_pem = ICP.get_param('mx_cfdi_sw.cer_pem') or ''
        key_pem = ICP.get_param('mx_cfdi_sw.key_pem') or ''
        key_pwd = ICP.get_param('mx_cfdi_sw.key_password') or ''
        return {
            'sandbox': sandbox,
            'base_url': base_url.rstrip('/'),
            'token': token,
            'user': user,
            'password': password,
            'rfc': rfc,
            'cer_pem': cer_pem,
            'key_pem': key_pem,
            'key_password': key_pwd,
        }

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
        url = cfg['base_url'] + '/cfdi33/issue/v4'  # ruta documentada
        files = {'xml': ('cfdi.xml', xml_bytes, 'application/xml')}
        # NO fijar Content-Type manualmente
        resp = requests.post(url, headers=self._headers(cfg), files=files, timeout=60)

        if resp.status_code >= 400:
            try:
                data = resp.json()
                msg = data.get('message') or data.get('Message') or resp.text
            except Exception:
                msg = resp.text
            raise UserError(_('Error timbrando con SW: %s') % msg)

        # Respuesta típica: JSON con uuid y cfdi (base64)
        data = resp.json() if resp.headers.get('Content-Type', '').startswith('application/json') else {}
        uuid = (data.get('data') or {}).get('uuid') or data.get('uuid') or data.get('Uuid') or ''
        xml_b64 = data.get('cfdi') or data.get('Cfdi') or None
        xml_timbrado = base64.b64decode(xml_b64) if xml_b64 else xml_bytes
        return {'uuid': uuid, 'xml_timbrado': xml_timbrado}

    @api.model
    def _cancel(self, uuid, rfc=None, cer_pem=None, key_pem=None, password=None, motivo='02', folio_sustitucion=None):
        """Cancelación vía CSD (JSON)."""
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg()
        rfc = rfc or cfg.get('rfc') or ''
        cer_pem = cer_pem or cfg.get('cer_pem') or ''
        key_pem = key_pem or cfg.get('key_pem') or ''
        password = password or cfg.get('key_password') or ''

        url = cfg['base_url'] + '/cfdi33/cancel/csd'  # versión v4
        payload = {
            'rfc': rfc,
            'b64Cer': base64.b64encode(cer_pem.encode('utf-8')).decode('ascii') if cer_pem else '',
            'b64Key': base64.b64encode(key_pem.encode('utf-8')).decode('ascii') if key_pem else '',
            'password': password or '',
            'uuid': uuid,
            'motivo': motivo,
            'folioSustitucion': folio_sustitucion or ''
        }
        resp = requests.post(url, headers=self._headers(cfg, json_ct=True),
                             data=json.dumps(payload), timeout=60)
        if resp.status_code >= 400:
            try:
                data = resp.json()
                msg = data.get('message') or data.get('Message') or resp.text
            except Exception:
                msg = resp.text
            raise UserError(_('Error al cancelar con SW: %s') % msg)

        data = resp.json() if resp.headers.get('Content-Type', '').startswith('application/json') else {}
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
    