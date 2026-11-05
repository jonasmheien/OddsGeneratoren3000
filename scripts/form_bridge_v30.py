"""Verified historical form for multiple league CSV schemas, with a guarded cache.

This is an optional personal-use data input, not a forecast source. Only results
with both full-time scores can affect the model. Football-data.co.uk permits
light personal automation (at most twice a week); preserve the 96-hour cache.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from form_bridge_v29 import (
    SOURCES, FORM_WINDOW, CACHE_INTERVAL, name_key, _date, _goal,
    _fetch, attach_additional_form,
)

SCHEMA_VERSION = 30
# Official extra-league CSVs useful for European opponents outside the eight
# sources already configured in v2.9. Same 96h cache and source restrictions.
SOURCES = {**SOURCES,
    'AUT': 'https://www.football-data.co.uk/new/AUT.csv',
    'FIN': 'https://www.football-data.co.uk/new/FIN.csv',
    'SWZ': 'https://www.football-data.co.uk/new/SWZ.csv',
    'ROU': 'https://www.football-data.co.uk/new/ROU.csv',
}


def parse_csv(data: bytes, division: str, now: datetime) -> list[dict]:
    """Support season files (HomeTeam/FTHG) and extra leagues (Home/HG).

    Never treat an upcoming match or absent full-time score as historical form.
    """
    if not isinstance(data, bytes) or not data or len(data) > 9_000_000:
        raise ValueError('Missing or unsupported CSV data')
    if now.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    try:
        content = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        content = data.decode('cp1252')
    reader = csv.DictReader(io.StringIO(content, newline=''))
    names = {str(name).strip().casefold().lstrip('\ufeff'): name
             for name in (reader.fieldnames or []) if name}

    def require(*candidates):
        for candidate in candidates:
            if candidate.casefold() in names:
                return names[candidate.casefold()]
        raise ValueError('Missing result column: ' + '/'.join(candidates))

    date_key = require('Date')
    home_key = require('HomeTeam', 'Home')
    away_key = require('AwayTeam', 'Away')
    hg_key = require('FTHG', 'HG')
    ag_key = require('FTAG', 'AG')
    completed = {}
    for record in reader:
        if not isinstance(record, dict):
            continue
        when = _date(record.get(date_key))
        if not when or not now - FORM_WINDOW <= when < now - timedelta(hours=12):
            continue
        home = name_key(record.get(home_key))
        away = name_key(record.get(away_key))
        hgoals = _goal(record.get(hg_key))
        agoals = _goal(record.get(ag_key))
        if not 2 <= len(home) <= 80 or not 2 <= len(away) <= 80:
            continue
        if home == away or hgoals is None or agoals is None:
            continue
        ident = hashlib.sha256(f'{division}|{when.date().isoformat()}|{home}|{away}'.encode()).hexdigest()[:20]
        record_id = f'fdc:{division}:match:{ident}'
        completed[record_id] = {
            'id': record_id, 'utcDate': when.isoformat(), 'status': 'FINISHED',
            'homeTeam': {'id': f'fdc:{division}:team:{home}', 'name': home, 'shortName': home},
            'awayTeam': {'id': f'fdc:{division}:team:{away}', 'name': away, 'shortName': away},
            'score': {'fullTime': {'home': hgoals, 'away': agoals}},
            'competition': {'code': f'FDC-{division}', 'name': division},
            'formSource': 'football-data.co.uk: verified full-time results',
        }
    return list(completed.values())


def load_cached_history(now: datetime, cache_path: Path, fetch=_fetch):
    """Refresh missing v2.9 sources once; otherwise obey a 96h download gap.

    The old v2.9 cache contains four valid leagues and four failed country files.
    One migration retry is permitted for the missing ones only. Subsequent
    scheduled runs reuse the migrated cache even if a source still fails.
    """
    if now.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    try:
        cache = json.loads(cache_path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    previous = [m for m in cache.get('matches', []) if isinstance(m, dict) and m.get('id')]
    last = cache.get('lastAttempt')
    try:
        attempted = datetime.fromisoformat(str(last))
    except (ValueError, TypeError):
        attempted = None
    recent = bool(attempted and attempted.tzinfo and
                  timedelta(0) <= now - attempted < CACHE_INTERVAL)
    covered = {str((m.get('competition') or {}).get('code', '')).removeprefix('FDC-')
               for m in previous}
    covered &= set(SOURCES)
    # A v3.0 cache is never downloaded again inside its 96-hour window.
    if recent and cache.get('schemaVersion') == SCHEMA_VERSION:
        return previous, {
            'mode': 'cached', 'sourceCount': len(covered),
            'completedFixtures': len(previous), 'lastAttempt': last, 'errors': [],
        }
    # One migration-specific retry: the formerly unreadable extra-league CSVs.
    to_fetch = [code for code in SOURCES if code not in covered] if recent else list(SOURCES)
    if not to_fetch:
        return previous, {'mode': 'cached', 'sourceCount': len(covered),
                          'completedFixtures': len(previous), 'lastAttempt': last, 'errors': []}
    season = (f'{now.year % 100:02d}{(now.year + 1) % 100:02d}'
              if now.month >= 7 else f'{(now.year - 1) % 100:02d}{now.year % 100:02d}')
    merged = {str(m['id']): m for m in previous}
    errors = []
    for code in to_fetch:
        url = SOURCES[code].format(season=season)
        try:
            # Only the real remote client needs pacing; offline tests supply fetch.
            if fetch is _fetch:
                time.sleep(0.7)
            rows = parse_csv(fetch(url), code, now)
            if not rows:
                raise ValueError('No completed matches inside the form window')
            for match in rows:
                merged[str(match['id'])] = match
        except (OSError, TimeoutError, ValueError, RuntimeError) as exc:
            errors.append(f'{code}: {type(exc).__name__}')
    def is_recent(entry):
        try:
            value = datetime.fromisoformat(str(entry['utcDate']))
            return (value.tzinfo is not None and
                    now - FORM_WINDOW <= value < now - timedelta(hours=12))
        except (KeyError, ValueError, TypeError):
            return False
    rows = [m for m in merged.values() if is_recent(m)]
    active_codes = {str((m.get('competition') or {}).get('code', '')).removeprefix('FDC-') for m in rows}
    payload = {'schemaVersion': SCHEMA_VERSION, 'lastAttempt': now.isoformat(),
               'sourcesOk': len(active_codes & set(SOURCES)),
               'source': 'football-data.co.uk', 'matches': rows}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return rows, {'mode': 'migration' if recent else 'fetched',
                  'sourceCount': payload['sourcesOk'], 'completedFixtures': len(rows),
                  'lastAttempt': now.isoformat(), 'errors': errors,
                  'attemptedSources': to_fetch}
