#mx_cfdi_provider_sw/models/provider_sw.py
# -*- coding: utf-8 -*-
import base64
import json
from odoo import models, api, _
from odoo.exceptions import UserError
import time
import logging
import hashlib
# --- DEBUG helpers ---
# Enmascara el token y devuelve una huella corta (prefix…suffix|sha1=XXXX).
# Útil para loggear sin exponer el token completo.
def _tok_fp(tok: str) -> str:
    try:
        t = (tok or '').strip()
        if not t:
            return 'none'
        import hashlib as _hh
        return f"{t[:6]}…{t[-4:]}|sha1={_hh.sha1(t.encode()).hexdigest()[:8]}"
    except Exception:
        return 'na'
    

_logger = logging.getLogger(__name__)

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

# Implementación del proveedor SW Sapien (REST) para timbrado/cancelación y utilidades asociadas (carga/verificación de CSD y descarga de XML).
class CfdiProviderSW(models.AbstractModel):
    _name = "mx.cfdi.engine.provider.sw"
    _inherit = "mx.cfdi.engine.provider.base"
    _description = "CFDI Provider - SW Sapien"

    # Arma la configuración de SW leyendo parámetros del sistema e información de la empresa emisora (RFC y CSD). Devuelve un dict con:
    #  sandbox/base_url/api_base_url/token/usuario/password/rfc/cer_b64/key_b64/key_password/token_fp.
    # Requiere empresa_id en contexto o como argumento.
    def _cfg(self, empresa_id=None):
        ICP = self.env['ir.config_parameter'].sudo()
    
        # --- GLOBAL (un solo login para todos) ---
        sandbox  = (ICP.get_param('mx_cfdi_sw.sandbox', '1') or '').lower() in ('1','true','yes')
        base_url = (ICP.get_param('mx_cfdi_sw.base_url') or
                    ('https://services.sw.com.mx' if not sandbox else 'https://services.test.sw.com.mx')).rstrip('/')
        api_base = 'https://api.sw.com.mx' if not sandbox else 'https://api.test.sw.com.mx'
        token    = ICP.get_param('mx_cfdi_sw.token') or ''
        user     = ICP.get_param('mx_cfdi_sw.user') or ''
        pwd      = ICP.get_param('mx_cfdi_sw.password') or ''
        key_pwd_default = ICP.get_param('mx_cfdi_sw.key_password') or ''
    
        # --- POR EMPRESA (CSD y RFC emisor) ---
        if not empresa_id:
            empresa_id = self.env.context.get('empresa_id')
        if not empresa_id:
            raise UserError(_('Se requiere empresa_id en el contexto o como parámetro'))
    
        emp = self.env['empresas.empresa'].browse(empresa_id)
        if not emp.exists():
            raise UserError(_('Empresa no encontrada'))
    
        def _as_str(v):
            return v.decode('ascii') if isinstance(v, (bytes, bytearray)) else (v or '')
    
        return {
            'sandbox': sandbox,
            'base_url': base_url,
            'api_base_url': api_base,
            'token': token,
            'user': user,
            'password': pwd,
            'rfc': (emp.rfc or '').upper(),                     # RFC de la empresa
            'cer_b64': _as_str(emp.cfdi_sw_cer_file),           # CSD por empresa
            'key_b64': _as_str(emp.cfdi_sw_key_file),           # CSD por empresa
            'key_password': emp.cfdi_sw_key_password or key_pwd_default,
            'token_fp': _tok_fp(token),
        }

    # Timbrado principal:
    #  - Verifica/carga CSD en SW si no existe.
    #  - Intenta múltiples endpoints (issue/stamp, cfdi40 y compat cfdi33).
    #  - En éxito: regresa {'uuid': str, 'xml_timbrado': bytes}.
    #  - En errores 4xx/5xx: normaliza mensajes y lanza UserError con diagnóstico.
    # Respeta parámetros de depuración (mx_cfdi_sw.debug_http, log_resp_body_kb, http_timeout).
    @api.model
    def _stamp_xml(self, xml_bytes):
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode('utf-8')

        cfg = self._cfg(self.env.context.get('empresa_id'))


        ICP = self.env['ir.config_parameter'].sudo()
        debug_http = (ICP.get_param('mx_cfdi_sw.debug_http', '0') or '').lower() in ('1','true','yes')

        resp_kb = int(ICP.get_param('mx_cfdi_sw.log_resp_body_kb', 16) or 16)

        if debug_http:
            _logger.warning("SW HTTP DEBUG | rfc=%s | token=%s | sandbox=%s",
                            cfg.get('rfc'), cfg.get('token_fp'), cfg.get('sandbox'))
            

        is_v40 = (b'Version="4.0"' in xml_bytes) or (b"Version='4.0'" in xml_bytes)

        # Asegura que el CSD esté cargado en SW (necesario para ISSUE)
        try:
            if not self._has_cert():
                self._upload_cert_from_company()
        except Exception as e:
            raise UserError(_("No pude verificar/cargar el CSD en SW: %s") % e)

        # Hosts a probar: base + espejo (prod/test) como fallback
        base = cfg['base_url'].rstrip('/')
        hosts = [base]

        # dentro de _stamp_xml, donde construyes base_paths:
        def _pats(ver):
            paths = [
                f'/{ver}/issue/v4', f'/{ver}/issue/v3', f'/{ver}/issue/v2', f'/{ver}/issue/v1', f'/{ver}/issue',
                f'/{ver}/stamp/v4', f'/{ver}/stamp/v3', f'/{ver}/stamp/v2', f'/{ver}/stamp/v1', f'/{ver}/stamp',
            ]
            # Agregar rutas cfdi33 para compatibilidad cuando es v4.0
            if ver == 'cfdi40':
                paths.extend([
                    '/cfdi33/issue/v4', '/cfdi33/issue/v3', '/cfdi33/issue/v2', '/cfdi33/issue/v1', '/cfdi33/issue',
                ])
            return paths

        # Usa la versión detectada del XML
        base_paths = _pats('cfdi40') if is_v40 else _pats('cfdi33')

        # Permite sobreescribir/inyectar paths desde parámetros del sistema
        ICP = self.env['ir.config_parameter'].sudo()
        forced = (ICP.get_param('mx_cfdi_sw.issue_path') or '').strip()
        
        extras = []
        for key in ('mx_cfdi_sw.issue_paths',):
            v = (ICP.get_param(key) or '').strip()
            if v:
                extras += [p.strip() for p in v.split(',') if p.strip()]


        paths = []
        for p in [forced] + extras + base_paths:
            if p and p not in paths:
                paths.append(p)

        # Timeout configurable
        try:
            req_timeout = int(ICP.get_param('mx_cfdi_sw.http_timeout', 60))
        except Exception:
            req_timeout = 60

        last_err = None
        if debug_http:
            _logger.warning("SW HTTP DEBUG | hosts=%s", hosts)
            _logger.warning("SW HTTP DEBUG | paths=%s", paths[:8] + (['...'] if len(paths) > 8 else []))

        for host in hosts:
            for p in paths:
                url = host.rstrip('/') + p
                try:
                    # Headers seguros (enmascara token si logueas)
                    hdrs = self._headers(cfg)
                    if debug_http:
                        _logger.warning("SW HTTP TRY | url=%s | token=%s", url, cfg.get('token_fp'))


                    resp = requests.post(url, headers=hdrs,
                                         files={'xml': ('cfdi.xml', xml_bytes, 'application/xml')},
                                         timeout=req_timeout)

                    ct = (resp.headers.get('Content-Type') or '').lower()
                    body = resp.text or ''
                    if debug_http:
                        _logger.warning("SW HTTP RESP | url=%s | code=%s | ct=%s | body<=%dkB:\n%s",
                                        url, resp.status_code, ct, resp_kb, body[:resp_kb*1024])


                except Exception as e:
                    last_err = f"{url} -> {e}"
                    continue

                # Éxito → extrae uuid + XML timbrado (puede venir en texto o en Base64)
                if resp.status_code < 400:
                    data = resp.json() if ('json' in ct) else {}
                    d = (data.get('data') or data) if isinstance(data, dict) else {}
                    uuid = d.get('uuid') or d.get('UUID') or ''
                    cfdi_val = (d.get('cfdi') or d.get('Cfdi') or d.get('xml') or
                                d.get('XML') or d.get('cfdiXml') or d.get('cfdiXML'))
                    if uuid and cfdi_val:
                        if isinstance(cfdi_val, (bytes, bytearray)):
                            xml_bytes_out = bytes(cfdi_val)
                        elif isinstance(cfdi_val, str) and cfdi_val.lstrip().startswith('<'):
                            # XML en texto plano
                            xml_bytes_out = cfdi_val.encode('utf-8')
                        else:
                            # XML en Base64
                            xml_bytes_out = base64.b64decode(cfdi_val)
                        return {'uuid': uuid, 'xml_timbrado': xml_bytes_out}
                    last_err = f"{url} -> respuesta sin uuid/cfdi"
                    continue


                # Normaliza errores de SW (para decidir retry vs fail)
                detail = body
                try:
                    j = resp.json()
                    msgs = []
                    if isinstance(j, dict):
                        if j.get('message') or j.get('Message'):
                            msgs.append(j.get('message') or j.get('Message'))
                        if j.get('messageDetail') or j.get('MessageDetail'):
                            msgs.append(j.get('messageDetail') or j.get('MessageDetail'))
                        for k in ('data','Data'):
                            dd = j.get(k) or {}
                            if isinstance(dd, dict) and (dd.get('messageDetail') or dd.get('MessageDetail')):
                                msgs.append(dd.get('messageDetail') or dd.get('MessageDetail'))
                            errs = dd.get('errors') or dd.get('Errors') or dd.get('detalle') or dd.get('Detalle')
                            if isinstance(errs, list):
                                msgs += [str(e) for e in errs if e]
                            elif isinstance(errs, dict):
                                msgs += [f"{a}: {b}" for a,b in errs.items()]
                            
                    if msgs:
                        detail = ' | '.join(msgs)
                except Exception:
                    pass

                low = (detail or '').lower()
                # 404/405 → prueba siguiente path/host
                if resp.status_code in (404, 405):
                    last_err = f"{url} -> {resp.status_code} {detail[:200]}"
                    continue
                
                # 400 → si trae detalle de validación, detén y muestra
                if resp.status_code == 400:
                    # errores típicos de validación (atributos faltantes, receptor/emisor, etc.)
                    if any(word in low for word in ('attribute', 'atributo', 'base', 'receptor', 'emisor', 'regimen', 'uso')):
                        raise UserError(_('Validación CFDI (400): %s') % detail[:800])
                    # solo reintenta si es el genérico "no clasificado" sin pistas útiles
                    if ('cfdi40999' in low) or ('no clasificado' in low):
                        last_err = f"{url} -> 400 {detail[:200]}"
                        continue

                # 401 → token
                if resp.status_code == 401:
                    j = {}
                    try:
                        j = resp.json()
                    except Exception:
                        pass
                    msg = (j.get('message') or j.get('Message') or body or resp.reason or '').strip()
                    code = (j.get('code') or j.get('Code') or '').lower()
                    if debug_http:
                        _logger.warning("SW 401 DIAG | url=%s | token=%s | code=%s | msg=%s",
                                        url, cfg.get('token_fp'), code, msg[:400])
                    low = msg.lower()
                    if 's2000' in low or 'saldo' in low:
                        raise UserError(_('SW: saldo de timbres agotado para el RFC %(rfc)s.') % {'rfc': cfg.get('rfc')})
                    # ← mensaje explícito cuando sea token/cuenta/entorno
                    raise UserError(_('SW 401 (no saldo): token inválido/expirado o de otra cuenta/entorno. '
                                      'RFC=%(rfc)s, url=%(url)s, detalle=%(det)s')
                                    % {'rfc': cfg.get('rfc'), 'url': url, 'det': msg[:300]})




                # Otros 4xx/5xx → falla inmediata
                raise UserError(_('Error timbrando con SW (%s): %s') % (p, detail[:800]))

        raise UserError(_('SW: sin endpoint activo para timbrar (probé: %s). Último error: %s')
                        % (', '.join(paths), (last_err or 'N/A')))

    # =========================== utils ===========================
    # Consulta el DataWarehouse "live" de SW por UUID y devuelve el primer
    # registro encontrado (dict) o None si aún no está disponible.
    def _dw_lookup(self, uuid):
        """Devuelve el objeto del DW para ese UUID o None si aún no aparece."""
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg(self.env.context.get('empresa_id'))
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

    # Hace polling al DataWarehouse hasta obtener el XML y, si existe, # el acuse de timbrado. Devuelve {'xml': bytes, 'acuse': bytes|None}.
    # Lanza UserError si no aparece tras 'tries' intentos (con 'delay' entre cada uno).
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
    
    # Sube a SW el CSD (CER/KEY/PASSWORD) tomando los binarios base64
    # guardados en la empresa. Útil cuando SW aún no tiene el CSD registrado.
    # Devuelve True o lanza UserError ante error de API.
    def _upload_cert_from_company(self):
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg(self.env.context.get('empresa_id'))
        ICP = self.env['ir.config_parameter'].sudo()               # <-- agrega
        debug_http = (ICP.get_param('mx_cfdi_sw.debug_http','0')   # <-- agrega
                      or '').lower() in ('1','true','yes')

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
        if debug_http:
            _logger.warning("SW HTTP TRY | url=%s | token=%s", url, cfg.get('token_fp'))


        r = requests.post(url, headers=self._headers(cfg, json_ct=True),
                          data=json.dumps(payload), timeout=60)
        if r.status_code >= 400:
            try:
                data = r.json(); msg = data.get('message') or data.get('Message') or r.text
            except Exception:
                msg = r.text
            raise UserError(_('SW: error al cargar CSD: %s') % msg)
        return True

    # Cancela un CFDI vía endpoint CSD de SW usando el CSD de la empresa.
    # Devuelve {'status': ..., 'acuse': bytes|None}. Lanza UserError si la API falla.
    def _cancel(self, uuid, rfc=None, cer_pem=None, key_pem=None, password=None,
                motivo='02', folio_sustitucion=None):
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg(self.env.context.get('empresa_id'))
        ICP = self.env['ir.config_parameter'].sudo()
        debug_http = (ICP.get_param('mx_cfdi_sw.debug_http', '0') or '').lower() in ('1','true','yes')

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
        if debug_http:
            _logger.warning("SW HTTP TRY | url=%s | token=%s", url, cfg.get('token_fp'))


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
    
    # Consulta a SW los certificados cargados y confirma si existe uno para el RFC de la empresa. Devuelve True/False con parsing robusto del JSON de respuesta.
    def _has_cert(self, rfc=None):
        if not requests:
            raise UserError(_('El módulo requests no está disponible.'))
        cfg = self._cfg(self.env.context.get('empresa_id'))
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
    
    # Construye encabezados HTTP para SW. Inserta Authorization Bearer si hay token.
    # Si 'json_ct' es True, añade 'Content-Type: application/json'.
    def _headers(self, cfg, *, json_ct=False):
        # No fijes Content-Type salvo que sea JSON; para multipart lo define requests.
        h = {}
        if json_ct:
            h['Content-Type'] = 'application/json'
        if cfg.get('token'):
            h['Authorization'] = f"Bearer {cfg['token']}"
        return h

    # Prueba conectividad con SW contra la raíz del host configurado.
    # Devuelve (ok: bool, mensaje: str) con el detalle del resultado.
    # Pensado para un botón de "Probar conexión".
    @api.model
    def _ping(self):
        """Verifica conectividad con SW.
        No existe /ping público; probamos la raíz y consideramos OK cualquier
        status <500 (incluye 200/401/403/404 según el edge/API gateway)."""
        if not requests:
            return False, 'Python package requests no disponible'
        cfg = self._cfg(self.env.context.get('empresa_id'))
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

    # =========================== Fin utils ===========================
    
    # =========================== debug / logs ===========================
    # Loggea una versión segura de la configuración (sin exponer token) y devuelve el dict con los campos resumidos para diagnósticos.
    def _debug_cfg(self):
        cfg = self._cfg(self.env.context.get('empresa_id'))
        safe = {
            'sandbox': cfg.get('sandbox'),
            'base_url': cfg.get('base_url'),
            'rfc': cfg.get('rfc'),
            'token_present': bool(cfg.get('token')),
            'token_fp': cfg.get('token_fp'),
            'cer_b64_len': len(cfg.get('cer_b64') or ''),
            'key_b64_len': len(cfg.get('key_b64') or ''),
            'has_pwd': bool(cfg.get('key_password')),
        }
        _logger.info("SW DEBUG CFG: %s", safe)
        return safe

    # Lista los certificados que SW reporta y loggea posibles vigencias por entrada.
    # Devuelve True. Útil solo para diagnóstico manual.
    def debug_list_certificates(self):
        """Listar lo que SW dice tener cargado y loggear vigencias si las expone."""
        if not requests:
            return False
        cfg = self._cfg(self.env.context.get('empresa_id'))
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
    
    # =========================== FIN debugs ===========================
    