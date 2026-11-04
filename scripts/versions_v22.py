"""Transparent, immutable revision archive for same-day OddsGeneratoren editions.

A changed/rejected pick is not labelled as a lost-value bet without evidence.
No extra API calls and no replacement of the existing result-history store.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ARCHIVE_DIR = Path('state/versions')
PUBLIC_INDEX = Path('site/data/versions.json')


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path.with_name(path.name + '.tmp')
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    target.replace(path)


def _picks(snapshot: dict):
    out = {}
    for p in (snapshot.get('recommendations') or []):
        if not isinstance(p, dict):
            continue
        mid = str(p.get('matchId') or '')
        market = str(p.get('market') or '')
        if mid and market:
            out[(mid, market)] = p
    return out


def _display(p: dict):
    return {
        'matchId': str(p.get('matchId') or ''),
        'market': p.get('market'),
        'home': p.get('home'),
        'away': p.get('away'),
        'label': p.get('label'),
        'price': p.get('price'),
        'category': p.get('category'),
        'kickoff': p.get('kickoff'),
    }


def compare_editions(old: dict, new: dict) -> dict:
    a, b = _picks(old), _picks(new)
    removed = [dict(_display(a[k]), reason='Ikke kvalifisert i den nye analysen; årsak ikke bekreftet')
               for k in a.keys() - b.keys()]
    added = [_display(b[k]) for k in b.keys() - a.keys()]
    prices = []
    for k in a.keys() & b.keys():
        old_price, new_price = a[k].get('price'), b[k].get('price')
        if old_price != new_price:
            prices.append({'matchId': k[0], 'market': k[1],
                           'oldPrice': old_price, 'newPrice': new_price})
    return {'removed': sorted(removed, key=lambda x: (x['matchId'], x['market'])),
            'added': sorted(added, key=lambda x: (x['matchId'], x['market'])),
            'repriced': sorted(prices, key=lambda x: (x['matchId'], x['market']))}


def record_revision(previous: dict, current: dict, root: Path):
    """Archive the *previous* edition before replacing it with the new one."""
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return None
    day = str(previous.get('editionDate') or previous.get('localDate') or '')
    next_day = str(current.get('localDate') or current.get('editionDate') or '')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day) or day != next_day:
        return None
    previous_generated = str(previous.get('generatedAt') or '')
    new_generated = str(current.get('generatedAt') or '')
    if previous_generated == new_generated:
        return None
    canonical = json.dumps({'prior': previous, 'next': current}, sort_keys=True,
                           ensure_ascii=False).encode('utf-8')
    digest = hashlib.sha256(canonical).hexdigest()[:12]
    stamp = re.sub(r'[^0-9]', '', new_generated)[:14] or datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    path = root / ARCHIVE_DIR / day / (stamp + '-' + digest + '.json')
    if path.exists():
        return path
    changes = compare_editions(previous, current)
    record = {
        'date': day, 'before': previous_generated, 'after': new_generated,
        'changeCounts': {key: len(changes[key]) for key in changes},
        **changes, 'previousEdition': previous,
        'note': 'Utelatt tips er ikke automatisk dokumentert å ha mistet oddsverdi.',
    }
    _write_json(path, record)
    return path


def publish_version_history(root: Path):
    source = root / ARCHIVE_DIR
    paths = sorted(source.glob('????-??-??/*.json'), reverse=True)[:40] if source.exists() else []
    summaries = []
    for p in paths:
        try:
            obj = json.loads(p.read_text(encoding='utf-8'))
            summaries.append({key: obj.get(key) for key in ('date', 'before', 'after', 'added', 'removed', 'repriced', 'changeCounts')})
        except (OSError, ValueError, TypeError):
            continue
    _write_json(root / PUBLIC_INDEX, summaries)
    return summaries
