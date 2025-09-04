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
        base_url = ICP.get_param('mx_cfdi_sw.base_url') or (
            'https://services.sw.com.mx' if not sandbox else 'https://services.test.sw.com.mx'
        )
        token = ICP.get_param('mx_cfdi_sw.token') or ''
        user = ICP.get_param('mx_cfdi_sw.user') or ''
        password = ICP.get_param('mx_cfdi_sw.password') or ''
        return {
            'sandbox': sandbox,
            'base_url': base_url.rstrip('/'),
            'token': token,
            'user': user,
            'password': password,
        }

    def _headers(self, cfg):
        h = {'Content-Type': 'application/json'}
        if cfg.get('token'):
            h['Authorization'] = 'Bearer %s' % cfg['token']
        return h

    @api.model
    def _ping(self):
        if not requests:
            return False, 'Python package requests no disponible'
        cfg = self._cfg()
        url = cfg['base_url'].rstrip('/') + '/ping'
        try:
            r = requests.get(url, headers=self._headers(cfg), timeout=10)
            if r.status_code < 400:
                return True, 'Conexión OK (%s)' % url
            return False, 'Respuesta %s: %s' % (r.status_code, r.text)
        except Exception as e:
            return False, 'Error de conexión: %s' % e

    @api.model
    def _stamp_xml(self, xml_bytes):
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg()
        url = cfg['base_url'] + '/cfdi40/stamp'
        payload = {
            'xml': base64.b64encode(xml_bytes).decode('ascii'),
        }
        resp = requests.post(url, headers=self._headers(cfg), data=json.dumps(payload), timeout=60)
        if resp.status_code >= 400:
            try:
                data = resp.json()
                msg = data.get('message') or data.get('Message') or resp.text
            except Exception:
                msg = resp.text
            raise UserError(_('Error timbrando con SW: %s') % msg)
        data = resp.json() if resp.headers.get('Content-Type', '').startswith('application/json') else {}
        uuid = (data.get('uuid') or data.get('Uuid') or '').strip()
        xml_b64 = data.get('cfdi') or data.get('Cfdi') or None
        xml_timbrado = base64.b64decode(xml_b64) if xml_b64 else xml_bytes
        return {'uuid': uuid, 'xml_timbrado': xml_timbrado}

    @api.model
    def _cancel(self, uuid, rfc=None, cer_pem=None, key_pem=None, password=None):
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg()
        url = cfg['base_url'] + '/cfdi40/cancel'
        payload = {
            'uuid': uuid,
            'rfc': rfc,
            'cer': cer_pem,
            'key': key_pem,
            'password': password or '',
        }
        resp = requests.post(url, headers=self._headers(cfg), data=json.dumps(payload), timeout=60)
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

    @api.model
    def _status(self, uuid, rfc=None):
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg()
        url = cfg['base_url'] + '/cfdi40/status/%s' % uuid
        resp = requests.get(url, headers=self._headers(cfg), timeout=30)
        if resp.status_code >= 400:
            raise UserError(_('Error consultando estatus en SW: %s') % (resp.text,))
        return resp.json() if resp.headers.get('Content-Type', '').startswith('application/json') else {'raw': resp.text}

