# -*- coding: utf-8 -*-
"""
Grafana Plugin for PegaProx
Embeds Grafana dashboards via iframe + proxies Grafana API calls
through PegaProx so the API key never leaves the server.

Config stored in plugins/grafana/config.json:
  grafana_url  : browser-accessible URL (used for iframes)
  api_url      : backend-accessible URL (for API calls, defaults to grafana_url)
  api_key      : Grafana service account token or API key
  verify_ssl   : bool, default False
  theme        : "dark" | "light", default "dark"
  org_id       : int, default 1
  pinned       : list of {uid, title, slug} - user-pinned dashboards
"""
import os
import json
import logging
import requests as _requests
from flask import request, Response, stream_with_context

from pegaprox.api.plugins import register_plugin_route

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PLUGIN_DIR, 'config.json')

_DEFAULT_CFG = {
    'grafana_url': '',
    'api_url': '',
    'api_key': '',
    'verify_ssl': False,
    'theme': 'dark',
    'org_id': 1,
    'pinned': []
}


# ─── Config helpers ───────────────────────────────────────────────

def _load_cfg():
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        # backfill missing keys
        for k, v in _DEFAULT_CFG.items():
            cfg.setdefault(k, v)
        return cfg
    except FileNotFoundError:
        return dict(_DEFAULT_CFG)
    except Exception as e:
        logging.warning(f'[grafana] Failed to load config: {e}')
        return dict(_DEFAULT_CFG)


def _save_cfg(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=4)


def _api_url(cfg):
    """Effective backend URL for API calls (falls back to grafana_url)"""
    return (cfg.get('api_url') or cfg.get('grafana_url') or '').rstrip('/')


def _grafana_session(cfg):
    s = _requests.Session()
    key = cfg.get('api_key', '')
    if key:
        s.headers['Authorization'] = f'Bearer {key}'
    s.headers['Accept'] = 'application/json'
    s.verify = cfg.get('verify_ssl', False)
    return s


# ─── Route handlers ───────────────────────────────────────────────

def _get_config():
    cfg = _load_cfg()
    # never send raw API key to frontend
    safe = dict(cfg)
    if safe.get('api_key'):
        safe['api_key'] = '***'
    safe['configured'] = bool(cfg.get('grafana_url'))
    return safe


def _update_config():
    data = request.get_json(silent=True) or {}
    cfg = _load_cfg()
    for field in ('grafana_url', 'api_url', 'verify_ssl', 'theme', 'org_id'):
        if field in data:
            cfg[field] = data[field]
    # only update key if a real value was sent (not the masked ***)
    if data.get('api_key') and data['api_key'] != '***':
        cfg['api_key'] = data['api_key']
    _save_cfg(cfg)
    return {'success': True}


def _test_connection():
    cfg = _load_cfg()
    base = _api_url(cfg)
    if not base:
        return {'success': False, 'error': 'Grafana URL not configured'}
    try:
        s = _grafana_session(cfg)
        r = s.get(f'{base}/api/health', timeout=8)
        if r.status_code == 200:
            data = r.json()
            return {
                'success': True,
                'version': data.get('version', '?'),
                'commit': data.get('commit', ''),
                'database': data.get('database', ''),
            }
        return {'success': False, 'error': f'HTTP {r.status_code}: {r.text[:200]}'}
    except _requests.exceptions.ConnectionError:
        return {'success': False, 'error': f'Cannot connect to {base}'}
    except _requests.exceptions.Timeout:
        return {'success': False, 'error': 'Connection timed out (8s)'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _list_dashboards():
    """Search all dashboards via Grafana API"""
    cfg = _load_cfg()
    base = _api_url(cfg)
    if not base:
        return {'error': 'Not configured', 'dashboards': []}
    try:
        s = _grafana_session(cfg)
        q = request.args.get('q', '')
        params = {'type': 'dash-db', 'limit': 200}
        if q:
            params['query'] = q
        r = s.get(f'{base}/api/search', params=params, timeout=10)
        if r.status_code != 200:
            return {'error': f'Grafana API error {r.status_code}', 'dashboards': []}
        items = r.json()
        # Normalize fields
        dashboards = [
            {
                'uid':   d.get('uid', ''),
                'title': d.get('title', 'Untitled'),
                'slug':  d.get('uri', '').replace('db/', ''),
                'url':   d.get('url', ''),
                'tags':  d.get('tags', []),
                'folder': d.get('folderTitle', ''),
                'type':  d.get('type', 'dash-db'),
            }
            for d in items if d.get('type') == 'dash-db'
        ]
        return {'dashboards': dashboards}
    except Exception as e:
        return {'error': str(e), 'dashboards': []}


def _pin_dashboard():
    """Add a dashboard to pinned list"""
    data = request.get_json(silent=True) or {}
    uid = data.get('uid', '').strip()
    if not uid:
        return {'error': 'uid required'}, 400
    cfg = _load_cfg()
    pinned = cfg.get('pinned', [])
    # avoid duplicates
    if not any(p['uid'] == uid for p in pinned):
        pinned.append({
            'uid':   uid,
            'title': data.get('title', uid),
            'slug':  data.get('slug', ''),
            'tags':  data.get('tags', []),
        })
        cfg['pinned'] = pinned
        _save_cfg(cfg)
    return {'success': True, 'pinned': cfg['pinned']}


def _unpin_dashboard():
    """Remove a dashboard from pinned list"""
    data = request.get_json(silent=True) or {}
    uid = data.get('uid', '').strip()
    if not uid:
        return {'error': 'uid required'}, 400
    cfg = _load_cfg()
    cfg['pinned'] = [p for p in cfg.get('pinned', []) if p['uid'] != uid]
    _save_cfg(cfg)
    return {'success': True, 'pinned': cfg['pinned']}


def _check_headers():
    """Fetch Grafana root and report headers that affect iframe embedding"""
    cfg = _load_cfg()
    base = _api_url(cfg)
    if not base:
        return {'success': False, 'error': 'Grafana URL not configured'}
    try:
        s = _grafana_session(cfg)
        r = s.get(f'{base}/', timeout=8, allow_redirects=True)
        hdrs = dict(r.headers)
        xfo = hdrs.get('X-Frame-Options', hdrs.get('x-frame-options', None))
        csp = hdrs.get('Content-Security-Policy', hdrs.get('content-security-policy', None))

        issues = []
        ok_embed = True

        if xfo:
            issues.append(f'X-Frame-Options: {xfo}  ← bloque les iframes')
            ok_embed = False
        else:
            issues.append('X-Frame-Options: absent ✓')

        if csp:
            if 'frame-ancestors' in csp:
                fa = [p for p in csp.split(';') if 'frame-ancestors' in p]
                if fa and "'self'" in fa[0] and '*' not in fa[0]:
                    issues.append(f'CSP frame-ancestors: {fa[0].strip()}  ← bloque les iframes')
                    ok_embed = False
                else:
                    issues.append(f'CSP frame-ancestors: {fa[0].strip() if fa else "?"} ✓')
            else:
                issues.append('CSP frame-ancestors: absent ✓')
        else:
            issues.append('Content-Security-Policy: absent ✓')

        fix = []
        if not ok_embed:
            fix.append('Dans grafana.ini :')
            fix.append('  [security]')
            fix.append('  allow_embedding = true')
            if csp and 'frame-ancestors' in csp:
                fix.append('  content_security_policy = false')
            fix.append('')
            fix.append('Docker : GF_SECURITY_ALLOW_EMBEDDING=true')
            if csp and 'frame-ancestors' in csp:
                fix.append('         GF_SECURITY_CONTENT_SECURITY_POLICY=false')

        return {
            'success': ok_embed,
            'http_status': r.status_code,
            'embed_ok': ok_embed,
            'issues': issues,
            'fix': fix if fix else ['Aucun blocage détecté — l\'iframe devrait fonctionner.'],
            'raw_xfo': xfo,
            'raw_csp': csp,
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _proxy_grafana():
    """
    Proxy all Grafana API requests.
    URL pattern: /api/plugins/grafana/api/proxy/<grafana_api_path>
    e.g. /api/plugins/grafana/api/proxy/api/dashboards/uid/abc123
         → forwards to http://grafana:3000/api/dashboards/uid/abc123
    """
    cfg = _load_cfg()
    base = _api_url(cfg)
    if not base:
        return Response('{"error":"Grafana not configured"}', status=503,
                        content_type='application/json')

    # Extract the Grafana path from the request URL
    full_path = request.path  # /api/plugins/grafana/api/proxy/<path>
    marker = '/api/plugins/grafana/api/proxy/'
    grafana_path = full_path.split(marker, 1)[-1] if marker in full_path else ''

    target = f'{base}/{grafana_path}'
    if request.query_string:
        target += '?' + request.query_string.decode('utf-8', errors='replace')

    try:
        s = _grafana_session(cfg)
        method = request.method.upper()
        body = request.get_data() if method in ('POST', 'PUT', 'PATCH') else None
        content_type = request.content_type or 'application/json'

        resp = s.request(
            method, target,
            data=body,
            headers={'Content-Type': content_type} if body else {},
            timeout=15,
            allow_redirects=True,
        )

        # Stream response back
        excluded_headers = {'transfer-encoding', 'content-encoding', 'connection'}
        headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in excluded_headers
        }
        return Response(resp.content, status=resp.status_code, headers=headers)

    except _requests.exceptions.ConnectionError:
        return Response(
            json.dumps({'error': f'Cannot connect to Grafana at {base}'}),
            status=503, content_type='application/json'
        )
    except _requests.exceptions.Timeout:
        return Response(
            json.dumps({'error': 'Grafana request timed out'}),
            status=504, content_type='application/json'
        )
    except Exception as e:
        logging.error(f'[grafana] proxy error: {e}')
        return Response(
            json.dumps({'error': str(e)}),
            status=500, content_type='application/json'
        )


# ─── Plugin registration ───────────────────────────────────────────

def register(app):
    register_plugin_route('grafana', 'config',         _get_config)
    register_plugin_route('grafana', 'config/save',    _update_config)
    register_plugin_route('grafana', 'test',           _test_connection)
    register_plugin_route('grafana', 'check-headers',  _check_headers)
    register_plugin_route('grafana', 'dashboards',     _list_dashboards)
    register_plugin_route('grafana', 'pin',            _pin_dashboard)
    register_plugin_route('grafana', 'unpin',          _unpin_dashboard)
    # proxy: registered as prefix — dispatcher will match proxy/* via prefix matching
    register_plugin_route('grafana', 'proxy',          _proxy_grafana)
    logging.info('[grafana] Plugin registered (proxy + dashboard browser)')
