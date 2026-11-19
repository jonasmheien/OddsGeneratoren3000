"""Short private cache for independent result feeds, never bookmaker prices."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from odds_budget_v55 import atomic_json, read_json
from result_sources_v51 import normalize_uefa


class Results(list):
    def __init__(self):
        super().__init__()
        self.diagnostics = []


def cached_fetch(root, provider, url, fetch, *, now=None):
    if root is None:
        return fetch()
    now = now or datetime.now(timezone.utc)
    # Callers supply public URLs; credentials live only in request headers.
    if urlsplit(url).hostname not in ('api.football-data.org', 'match.uefa.com', 'api.sportmonks.com'):
        raise ValueError('Unexpected result source')
    token = hashlib.sha256((provider + '|' + url).encode()).hexdigest()
    path = Path(root) / '.cache/results-v55' / (token + '.json')
    saved = read_json(path)
    if saved and 0 <= now.timestamp() - saved['savedAt'] < 600:
        return saved['data']
    data = fetch()
    atomic_json(path, {'savedAt': now.timestamp(), 'data': data})
    return data


def verified_evidence(root):
    """Replay saved official rows through the same validation as live results."""
    data = read_json(Path(root) / 'data/verified-results-v55.json')
    if data is None:
        return []
    if data.get('schemaVersion') != 55:
        raise ValueError('Unknown official result evidence')
    rows = []
    for response in data.get('responses', []):
        url = response['url']
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname != 'match.uefa.com' or parsed.path != '/v5/matches':
            raise ValueError('Unexpected official result evidence source')
        for raw in response['matches']:
            row = normalize_uefa(raw, url, response['competition'])
            if row and row['status'] == 'FINISHED':
                rows.append(row)
    return rows
