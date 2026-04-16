# -*- coding: utf-8 -*-
"""
Zammad Plugin for PegaProx
Integrates Zammad helpdesk: ticket stats on main dashboard,
full ticket history per client, cluster ↔ organization linking.

Config stored in plugins/zammad/config.json:
  zammad_url   : Zammad instance URL
  api_token    : Zammad API token (Settings > API > Token Access)
  verify_ssl   : bool, default True
  links        : {cluster_id: {org_id, org_name, cluster_name}}
"""
import os
import json
import logging
from datetime import datetime, timezone
import requests as _requests
from flask import request, Response

from pegaprox.api.plugins import register_plugin_route

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PLUGIN_DIR, 'config.json')

_DEFAULT_CFG = {
    'zammad_url': '',
    'api_token': '',
    'verify_ssl': True,
    'links': {}
}


# ─── Config helpers ───────────────────────────────────────────────

def _load_cfg():
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        for k, v in _DEFAULT_CFG.items():
            cfg.setdefault(k, v)
        return cfg
    except FileNotFoundError:
        return dict(_DEFAULT_CFG)
    except Exception as e:
        logging.warning(f'[zammad] Failed to load config: {e}')
        return dict(_DEFAULT_CFG)


def _save_cfg(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=4)


def _base_url(cfg):
    return (cfg.get('zammad_url') or '').rstrip('/')


def _session(cfg):
    s = _requests.Session()
    token = cfg.get('api_token', '')
    if token:
        s.headers['Authorization'] = f'Token token={token}'
    s.headers['Content-Type'] = 'application/json'
    s.verify = cfg.get('verify_ssl', True)
    return s


def _parse_dt(s):
    """Parse ISO datetime string to datetime object"""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return None


def _format_minutes(minutes):
    """Format minutes to human readable string"""
    if minutes is None:
        return None
    m = int(minutes)
    if m < 60:
        return f'{m} min'
    h = m // 60
    rem = m % 60
    if rem == 0:
        return f'{h}h'
    return f'{h}h {rem}m'


# ─── Route handlers ───────────────────────────────────────────────

def _get_config():
    cfg = _load_cfg()
    safe = dict(cfg)
    if safe.get('api_token'):
        safe['api_token'] = '***'
    safe['configured'] = bool(cfg.get('zammad_url'))
    return safe


def _update_config():
    data = request.get_json(silent=True) or {}
    cfg = _load_cfg()
    for field in ('zammad_url', 'verify_ssl'):
        if field in data:
            cfg[field] = data[field]
    if data.get('api_token') and data['api_token'] != '***':
        cfg['api_token'] = data['api_token']
    _save_cfg(cfg)
    return {'success': True}


def _test_connection():
    cfg = _load_cfg()
    base = _base_url(cfg)
    if not base:
        return {'success': False, 'error': 'URL Zammad non configurée'}
    try:
        s = _session(cfg)
        r = s.get(f'{base}/api/v1/users/me', timeout=8)
        if r.status_code == 200:
            u = r.json()
            return {
                'success': True,
                'login': u.get('login', '?'),
                'name': f"{u.get('firstname', '')} {u.get('lastname', '')}".strip(),
                'email': u.get('email', ''),
                'role': ', '.join(u.get('role_ids', []).__class__.__name__ and
                                  [str(x) for x in u.get('role_ids', [])]),
            }
        return {'success': False, 'error': f'HTTP {r.status_code}: {r.text[:200]}'}
    except _requests.exceptions.ConnectionError:
        return {'success': False, 'error': f'Impossible de se connecter à {base}'}
    except _requests.exceptions.Timeout:
        return {'success': False, 'error': 'Timeout (8s)'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _get_stats():
    """Ticket stats for the main dashboard KPI widget"""
    cfg = _load_cfg()
    base = _base_url(cfg)
    if not base:
        return {'configured': False, 'open': 0, 'pending': 0, 'avg_response_min': None, 'avg_response_fmt': None}

    try:
        s = _session(cfg)

        # Open tickets (state: new + open)
        open_count = 0
        r = s.get(f'{base}/api/v1/tickets/search', params={
            'query': 'state.name:new OR state.name:open',
            'limit': 1, 'page': 1,
        }, timeout=10)
        if r.status_code == 200:
            d = r.json()
            open_count = d.get('tickets_count', len(d.get('tickets', [])))

        # Pending tickets
        pending_count = 0
        r = s.get(f'{base}/api/v1/tickets/search', params={
            'query': 'state.name:"pending reminder" OR state.name:"pending close"',
            'limit': 1, 'page': 1,
        }, timeout=10)
        if r.status_code == 200:
            d = r.json()
            pending_count = d.get('tickets_count', len(d.get('tickets', [])))

        # Avg first response time from recent closed tickets
        avg_response_min = None
        r = s.get(f'{base}/api/v1/tickets', params={
            'per_page': 30, 'page': 1,
            'sort_by': 'updated_at', 'order_by': 'desc',
        }, timeout=10)
        if r.status_code == 200:
            tickets = r.json()
            if isinstance(tickets, dict):
                tickets = tickets.get('tickets', [])
            deltas = []
            for t in tickets:
                if not isinstance(t, dict):
                    continue
                created = _parse_dt(t.get('created_at'))
                first_resp = _parse_dt(t.get('first_response_at'))
                if created and first_resp:
                    diff = (first_resp - created).total_seconds() / 60
                    if 0 < diff < 10000:
                        deltas.append(diff)
            if deltas:
                avg_response_min = sum(deltas) / len(deltas)

        return {
            'configured': True,
            'open': open_count,
            'pending': pending_count,
            'avg_response_min': round(avg_response_min) if avg_response_min else None,
            'avg_response_fmt': _format_minutes(avg_response_min) if avg_response_min else None,
        }
    except Exception as e:
        logging.warning(f'[zammad] stats error: {e}')
        return {'configured': True, 'open': 0, 'pending': 0,
                'avg_response_min': None, 'avg_response_fmt': None, 'error': str(e)}


def _list_tickets():
    """List tickets with optional org/state/cluster filters"""
    cfg = _load_cfg()
    base = _base_url(cfg)
    if not base:
        return {'error': 'Non configuré', 'tickets': [], 'total': 0}
    try:
        s = _session(cfg)
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(50, max(5, int(request.args.get('per_page', 25))))
        state = request.args.get('state', 'all')
        cluster_id = request.args.get('cluster_id', '')
        q = request.args.get('q', '').strip()

        # Resolve org from cluster link
        org_id = request.args.get('org_id', '')
        if cluster_id and not org_id:
            link = cfg.get('links', {}).get(cluster_id, {})
            org_id = str(link.get('org_id', ''))

        # Build search query
        parts = []
        if state and state != 'all':
            state_map = {
                'open':    'state.name:new OR state.name:open',
                'pending': 'state.name:"pending reminder" OR state.name:"pending close"',
                'closed':  'state.name:closed',
            }
            parts.append(state_map.get(state, f'state.name:{state}'))
        if org_id:
            parts.append(f'organization.id:{org_id}')
        if q:
            parts.append(q)

        total = 0
        tickets_raw = []

        if parts:
            query = ' AND '.join(f'({p})' for p in parts)
            r = s.get(f'{base}/api/v1/tickets/search', params={
                'query': query,
                'limit': per_page,
                'page': page,
                'expand': True,
            }, timeout=15)
            if r.status_code == 200:
                d = r.json()
                tickets_raw = d.get('tickets', d) if isinstance(d, dict) else d
                total = d.get('tickets_count', len(tickets_raw)) if isinstance(d, dict) else len(tickets_raw)
        else:
            r = s.get(f'{base}/api/v1/tickets', params={
                'per_page': per_page,
                'page': page,
                'sort_by': 'updated_at',
                'order_by': 'desc',
                'expand': True,
            }, timeout=15)
            if r.status_code == 200:
                tickets_raw = r.json()
                if isinstance(tickets_raw, dict):
                    tickets_raw = tickets_raw.get('tickets', [])
                total = len(tickets_raw)  # approximate

        tickets = []
        for t in tickets_raw:
            if not isinstance(t, dict):
                continue
            # State normalization
            state_val = t.get('state') or t.get('state_id', '')
            priority_val = t.get('priority') or t.get('priority_id', '')
            tickets.append({
                'id':               t.get('id'),
                'number':           t.get('number'),
                'title':            t.get('title', '(sans titre)'),
                'state':            str(state_val),
                'priority':         str(priority_val),
                'customer':         t.get('customer') or '',
                'organization':     t.get('organization') or '',
                'created_at':       t.get('created_at'),
                'updated_at':       t.get('updated_at'),
                'first_response_at': t.get('first_response_at'),
                'close_at':         t.get('close_at'),
                'url':              f'{base}/#ticket/zoom/{t.get("id")}',
            })

        return {'tickets': tickets, 'total': total, 'page': page, 'per_page': per_page}
    except Exception as e:
        logging.error(f'[zammad] list tickets error: {e}')
        return {'error': str(e), 'tickets': [], 'total': 0}


def _list_organizations():
    """List Zammad organizations for cluster linking"""
    cfg = _load_cfg()
    base = _base_url(cfg)
    if not base:
        return {'error': 'Non configuré', 'organizations': []}
    try:
        s = _session(cfg)
        q = request.args.get('q', '').strip()
        if q:
            r = s.get(f'{base}/api/v1/organizations/search', params={'query': q, 'limit': 25}, timeout=10)
        else:
            r = s.get(f'{base}/api/v1/organizations', params={'per_page': 50, 'page': 1}, timeout=10)
        if r.status_code != 200:
            return {'error': f'HTTP {r.status_code}', 'organizations': []}
        items = r.json()
        orgs = [
            {'id': o.get('id'), 'name': o.get('name', '?'), 'note': o.get('note', '')}
            for o in (items if isinstance(items, list) else [])
            if isinstance(o, dict)
        ]
        return {'organizations': orgs}
    except Exception as e:
        return {'error': str(e), 'organizations': []}


def _get_links():
    cfg = _load_cfg()
    return {'links': cfg.get('links', {})}


def _set_link():
    """Link or unlink a cluster to a Zammad organization"""
    data = request.get_json(silent=True) or {}
    cluster_id = str(data.get('cluster_id', '')).strip()
    if not cluster_id:
        return {'error': 'cluster_id requis'}, 400
    cfg = _load_cfg()
    org_id = data.get('org_id')
    if org_id:
        cfg.setdefault('links', {})[cluster_id] = {
            'org_id':       org_id,
            'org_name':     data.get('org_name', ''),
            'cluster_name': data.get('cluster_name', cluster_id),
        }
    else:
        cfg.get('links', {}).pop(cluster_id, None)
    _save_cfg(cfg)
    return {'success': True, 'links': cfg.get('links', {})}


# ─── Plugin registration ───────────────────────────────────────────

def register(app):
    register_plugin_route('zammad', 'config',        _get_config)
    register_plugin_route('zammad', 'config/save',   _update_config)
    register_plugin_route('zammad', 'test',          _test_connection)
    register_plugin_route('zammad', 'stats',         _get_stats)
    register_plugin_route('zammad', 'tickets',       _list_tickets)
    register_plugin_route('zammad', 'organizations', _list_organizations)
    register_plugin_route('zammad', 'links',         _get_links)
    register_plugin_route('zammad', 'link',          _set_link)
    logging.info('[zammad] Plugin registered')
