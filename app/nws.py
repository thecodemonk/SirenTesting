"""National Weather Service active-alerts client.

Fetches active alerts for the configured zone from the public NWS API
(https://api.weather.gov — no API key, but a User-Agent is required) and caches
the result in memory for a short TTL so page renders don't hammer the API.
On any failure it serves the last good payload (or an empty list) rather than
raising, so a weather.gov outage never takes the site down.
"""
import time

import requests
from flask import current_app

NWS_ALERTS_URL = 'https://api.weather.gov/alerts/active'
_CACHE_TTL = 60  # seconds
# Module-level cache — per gunicorn worker, which is fine for this scale.
_cache = {'ts': 0.0, 'alerts': []}


def _parse(feature):
    p = feature.get('properties', {})
    return {
        'id': feature.get('id'),
        'event': p.get('event'),
        'headline': p.get('headline'),
        'severity': p.get('severity'),
        'urgency': p.get('urgency'),
        'certainty': p.get('certainty'),
        'area_desc': p.get('areaDesc'),
        'effective': p.get('effective'),
        'expires': p.get('expires'),
        'description': p.get('description'),
        'instruction': p.get('instruction'),
        'geometry': feature.get('geometry'),  # GeoJSON, used by the map
    }


def get_active_alerts(force=False):
    """Return a list of parsed active alerts for the configured NWS zone."""
    now = time.time()
    if not force and _cache['ts'] and (now - _cache['ts']) < _CACHE_TTL:
        return _cache['alerts']

    zone = current_app.config.get('NWS_ZONE', 'MIC147')
    ua = current_app.config.get('NWS_USER_AGENT', '(sccarpsc.org, noreply@sccarpsc.org)')
    try:
        resp = requests.get(
            NWS_ALERTS_URL,
            params={'zone': zone},
            headers={'User-Agent': ua, 'Accept': 'application/geo+json'},
            timeout=5,
        )
        resp.raise_for_status()
        features = resp.json().get('features', [])
        _cache['alerts'] = [_parse(f) for f in features]
        _cache['ts'] = now
    except Exception as e:  # noqa: BLE001 — never let weather.gov break the page
        current_app.logger.warning(f'NWS alerts fetch failed: {e}')
        # Fall through to whatever we last had (possibly empty)
    return _cache['alerts']
