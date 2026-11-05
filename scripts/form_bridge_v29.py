"""Supplement verified club form from football-data.co.uk CSV archives.

This optional personal-research integration is light: at most one cache refresh
per 96 hours (<= twice a week). No bookmaker odds are imported as forecasts.
Only completed, independently scored games are allowed into model history.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

# The first four are European leagues outside the normal free football-data.org
# coverage. The others help qualify Nordic / Polish clubs on UEFA matchdays.
SOURCES = {
    'B1': 'https://www.football-data.co.uk/mmz4281/{season}/B1.csv',
    'T1': 'https://www.football-data.co.uk/mmz4281/{season}/T1.csv',
    'G1': 'https://www.football-data.co.uk/mmz4281/{season}/G1.csv',
    'SC0': 'https://www.football-data.co.uk/mmz4281/{season}/SC0.csv',
    'NOR': 'https://www.football-data.co.uk/new/NOR.csv',
    'SWE': 'https://www.football-data.co.uk/new/SWE.csv',
    'DNK': 'https://www.football-data.co.uk/new/DNK.csv',
    'POL': 'https://www.football-data.co.uk/new/POL.csv',
}
CACHE_INTERVAL = timedelta(hours=96)
FORM_WINDOW = timedelta(days=180)
NAMES = {
    'fenerbahce sk': 'fenerbahce', 'fenerbahce': 'fenerbahce',
    'besiktas jk': 'besiktas', 'besiktas': 'besiktas',
    'galatasaray sk': 'galatasaray', 'galatasaray': 'galatasaray',
    'fc midtjylland': 'midtjylland', 'midtjylland': 'midtjylland',
    'fc copenhagen': 'kobenhavn', 'fc kobenhavn': 'kobenhavn',
    'fc kopenhagen': 'kobenhavn', 'kobenhavn': 'kobenhavn',
    'malmo ff': 'malmo', 'malmo': 'malmo',
    'mjallby aif': 'mjallby', 'mjallby': 'mjallby',
    'fk bodo glimt': 'bodo glimt', 'bodo glimt': 'bodo glimt',
    'jagiellonia bialystok': 'jagiellonia', 'jagiellonia': 'jagiellonia',
    'lech poznan': 'lech poznan', 'lech poznan': 'lech poznan',
    'sporting braga': 'braga', 'sc braga': 'braga', 'braga': 'braga',
    'legia warszawa': 'legia warszawa', 'legia': 'legia warszawa',
}


def name_key(value):
    cleaned = unicodedata.normalize('NFKD', str(value or '').casefold())
    cleaned = ''.join(ch for ch in cleaned if not unicodedata.combining(ch))
    cleaned = cleaned.replace('ø', 'o').replace('æ', 'ae').replace('å', 'a')
    cleaned = re.sub(r'[^a-z0-9]+', ' ', cleaned).strip()
    return NAMES.get(cleaned, cleaned)


def _date(value):
    value = str(value or '').strip()
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d', '%d-%m-%Y', '%d-%m-%y'):
        try:
            return datetime.strptime(value, fmt).replace(hour=12, tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _goal(value):
    try:
        s = str(value).strip()
        n = int(s)
        if 0 <= n <= 30 and s == str(n):
            return n
    except (TypeError, ValueError):
        pass
    return None


def parse_csv(data: bytes, division: str, now: datetime) -> list[dict]:
    """Return scored matches only, with date/team key and collision-safe IDs."""
    if not isinstance(data, bytes) or len(data) > 9_000_000:
        raise ValueError('Unsupported CSV size')
    try:
        raw = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raw = data.decode('cp1252')
    if now.tzinfo is None:
        raise ValueError('timezone required')
    reader = csv.DictReader(io.StringIO(raw, newline=''))
    if not reader.fieldnames or not {'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG'}.issubset(reader.fieldnames):
        raise ValueError('Missing necessary score fields')
    rows = []
    for row in reader:
        if not isinstance(row, dict):
            continue
        dt = _date(row.get('Date'))
        if not dt or not now - FORM_WINDOW <= dt < now - timedelta(hours=12):
            continue  # Do not treat same-day or future fixtures as completed.
        home, away = name_key(row.get('HomeTeam')), name_key(row.get('AwayTeam'))
        hg, ag = _goal(row.get('FTHG')), _goal(row.get('FTAG'))
        if not home or not away or home == away or hg is None or ag is None:
            continue
        if not (2 <= len(home) <= 80 and 2 <= len(away) <= 80):
            continue
        ident = hashlib.sha256(f'{division}|{dt.date().isoformat()}|{home}|{away}'.encode()).hexdigest()[:20]
        home_id, away_id = f'fdc:{division}:team:{home}', f'fdc:{division}:team:{away}'
        rows.append({
            'id': f'fdc:{division}:match:{ident}',
            'utcDate': dt.isoformat(), 'status': 'FINISHED',
            'homeTeam': {'id': home_id, 'name': home, 'shortName': home},
            'awayTeam': {'id': away_id, 'name': away, 'shortName': away},
            'score': {'fullTime': {'home': hg, 'away': ag}},
            'competition': {'code': f'FDC-{division}', 'name': division},
            'formSource': 'football-data.co.uk: completed domestic league result',
        })
    unique = {r['id']: r for r in rows}
    return list(unique.values())


def _fetch(url):
    request = Request(url, headers={'User-Agent': 'OddsGeneratoren-3000/2.9 (private, weekly football form research)'})
    with urlopen(request, timeout=17) as response:
        data = response.read(9_000_001)
    if len(data) > 9_000_000:
        raise ValueError('CSV too large')
    return data


def load_cached_history(now: datetime, cache_path: Path, fetch=_fetch):
    """Never request each source more often than every 96 hours, even on error."""
    if now.tzinfo is None:
        raise ValueError('timezone required')
    cache = None
    try:
        cache = json.loads(cache_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    if isinstance(cache, dict):
        last = cache.get('lastAttempt')
        try:
            attempted = datetime.fromisoformat(last)
        except (TypeError, ValueError):
            attempted = None
        if attempted and attempted.tzinfo and now - attempted < CACHE_INTERVAL:
            rows = [m for m in cache.get('matches', []) if isinstance(m, dict)]
            return rows, {'mode': 'cached', 'sourceCount': cache.get('sourcesOk', 0),
                          'completedFixtures': len(rows), 'lastAttempt': last, 'errors': []}
    rows, issues, ok = [], [], 0
    season = f'{now.year % 100:02d}{(now.year + 1) % 100:02d}' if now.month >= 7 else f'{(now.year - 1) % 100:02d}{now.year % 100:02d}'
    for code, template in SOURCES.items():
        if fetch is _fetch:
            time.sleep(0.7)  # Polite rate limit for a small personal-use download.
        url = template.format(season=season)
        try:
            parsed = parse_csv(fetch(url), code, now)
            if not parsed:
                raise ValueError('No recently completed matches')
            rows.extend(parsed)
            ok += 1
        except (OSError, TimeoutError, ValueError, RuntimeError) as exc:
            issues.append(f'{code}: {type(exc).__name__}')
    # If an endpoint fails, keep the most recent verified rows as a fallback;
    # no invented/empty source can erase previously collected completed games.
    if isinstance(cache, dict) and cache.get('matches'):
        merged = {r['id']: r for r in cache['matches'] if isinstance(r, dict) and 'id' in r}
        merged.update({r['id']: r for r in rows})
        rows = list(merged.values())
    # Keep only recent results, no raw CSV and no historical bookmaker prices.
    # Keep only verified recent match records; never store raw CSV or bookmaker odds.
    def fresh_row(r):
        try:
            d = datetime.fromisoformat(r['utcDate'])
            return d.tzinfo is not None and now - FORM_WINDOW <= d < now
        except (ValueError, TypeError, KeyError):
            return False
    rows = [r for r in rows if fresh_row(r)]
    payload = {'lastAttempt': now.isoformat(), 'sourcesOk': ok,
               'source': 'football-data.co.uk', 'matches': rows}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return rows, {'mode': 'fetched', 'sourceCount': ok, 'completedFixtures': len(rows),
                  'lastAttempt': now.isoformat(), 'errors': issues}


def attach_additional_form(fixtures: list[dict], extra: list[dict], score_fn):
    """Only replace unmatched synthetic IDs, never overwrite official IDs."""
    club_games = defaultdict(int)
    for m in extra:
        if not isinstance(m, dict) or m.get('status') != 'FINISHED':
            continue
        for side in ('homeTeam', 'awayTeam'):
            team = m.get(side) or {}
            if team.get('id'):
                club_games[team['id']] += 1
    candidates = [(team_id, team_id.split(':team:', 1)[-1]) for team_id, count in club_games.items() if count >= 5]
    # Prefer exact canonical identities; reject ambiguous partial-name links.
    applied = 0
    linked_matches = 0
    for m in fixtures:
        if not str(m.get('id', '')).startswith('odds:'):
            continue
        changed = False
        for side in ('homeTeam', 'awayTeam'):
            t = m.get(side) or {}
            if not str(t.get('id', '')).startswith(('odds-home:', 'odds-away:')):
                continue
            raw_names = [name_key(t.get(k)) for k in ('name', 'shortName') if t.get(k)]
            found = []
            for team_id, name in candidates:
                score = max((1.0 if a == name else float(score_fn(a, name)) for a in raw_names), default=0.0)
                if score >= .91:
                    found.append((score, team_id))
            found.sort(reverse=True)
            if not found or (len(found) > 1 and found[0][0] - found[1][0] < .08):
                continue
            if found[0][1] == (m.get('awayTeam' if side == 'homeTeam' else 'homeTeam') or {}).get('id'):
                continue
            t['id'] = found[0][1]
            applied += 1
            changed = True
        if changed:
            m['formSource'] = 'verified domestic match results, additional football-data.co.uk coverage'
            linked_matches += 1
    existing = {str(m['id']): m for m in fixtures if isinstance(m, dict) and m.get('id')}
    for m in extra:
        if m.get('id'):
            existing.setdefault(str(m['id']), m)
    return list(existing.values()), {'teamsLinked': applied, 'fixturesTouched': linked_matches,
                                     'historyMatches': len(extra)}
