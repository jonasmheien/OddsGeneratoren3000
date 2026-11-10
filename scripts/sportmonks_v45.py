"""Sportmonks Football API v3: source-backed Danish and Scottish fixture history.

Only the free-plan leagues (and their playoffs) are admitted. No synthetic odds,
models or unverified results. Never put the private token in request URLs/logs.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE = 'https://api.sportmonks.com/v3/football'
OSLO = ZoneInfo('Europe/Oslo')
# Source: Sportmonks free plan, league IDs 271/501; playoffs 1659/513.
LEAGUES = {
    271: ('SM-DK1', 'Superliga'),
    1659: ('SM-DK1', 'Superliga Play-offs'),
    501: ('SM-SC1', 'Scottish Premiership'),
    513: ('SM-SC1', 'Scottish Premiership Play-offs'),
}


def fetch_page(url: str, token: str) -> dict:
    """API key in Authorization header, not in printed URLs."""
    request = Request(url, headers={'Authorization': token,
                                    'Accept': 'application/json',
                                    'User-Agent': 'OddsGeneratoren3000/4.5'})
    with urlopen(request, timeout=25) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError('Oversized response')
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get('data'), list):
        raise ValueError('Unexpected Sportmonks payload')
    return data


def _valid_id(value):
    return type(value) is int and value > 0


def _utc_start(item):
    seconds = item.get('starting_at_timestamp')
    if type(seconds) is int and seconds > 0:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    raw = item.get('starting_at')
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        # Sportmonks' API default timezone for starting_at is UTC.
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _participants(item):
    participants = item.get('participants')
    if not isinstance(participants, list):
        return None
    by_side = {}
    for team in participants:
        if not isinstance(team, dict):
            continue
        side = (team.get('meta') or {}).get('location')
        name = team.get('name')
        if side not in ('home', 'away') or side in by_side:
            return None
        if not _valid_id(team.get('id')) or not isinstance(name, str) or not (2 <= len(name.strip()) <= 100):
            return None
        by_side[side] = {'id': 'sm:' + str(team['id']), 'name': name.strip(),
                         'shortName': name.strip(), 'crest': None}
    if set(by_side) != {'home', 'away'} or by_side['home']['id'] == by_side['away']['id']:
        return None
    return by_side


def _goals(item, description):
    scores = item.get('scores') or []
    if not isinstance(scores, list):
        return None
    by_side = {}
    for line in scores:
        if not isinstance(line, dict) or line.get('description') != description:
            continue
        score = line.get('score') or {}
        side, goals = score.get('participant'), score.get('goals')
        if side not in ('home', 'away') or side in by_side:
            return None
        if type(goals) is not int or not 0 <= goals <= 30:
            return None
        by_side[side] = goals
    return by_side if set(by_side) == {'home', 'away'} else None


def normalize(item, now: datetime) -> dict | None:
    """Convert one documented Sportmonks event to the existing fixture contract."""
    if not isinstance(item, dict) or not _valid_id(item.get('id')):
        return None
    league_id = item.get('league_id')
    if league_id not in LEAGUES:
        return None
    start = _utc_start(item)
    teams = _participants(item)
    if start is None or teams is None:
        return None
    state = item.get('state_id')
    if state == 1 and start > now:
        status, score = 'SCHEDULED', {'fullTime': {'home': None, 'away': None}}
    elif state in (5, 7, 8) and start < now:
        # Play-offs can have ET/penalties. CURRENT includes extra time; for model
        # history we need explicit 90-minute 2ND_HALF totals instead.
        regular = _goals(item, '2ND_HALF') if state in (7, 8) else (
            _goals(item, '2ND_HALF') or _goals(item, 'CURRENT'))
        if regular is None:
            return None
        status = 'FINISHED'
        score = {'fullTime': regular, 'regularTime': regular, 'duration': 'REGULAR'}
    else:
        return None
    code, league_name = LEAGUES[league_id]
    return {'id': 'sm-match:' + str(item['id']), 'utcDate': start.isoformat(),
            'status': status,
            'homeTeam': teams['home'], 'awayTeam': teams['away'],
            'competition': {'code': code, 'name': league_name, 'emblem': None},
            'score': score,
            'formSource': 'Sportmonks', 'fixtureSource': 'Sportmonks free-plan fixtures'}


def discover(target_date: date, now: datetime, token: str, *, request=None,
             max_pages: int = 12) -> tuple[list[dict], dict]:
    """Source data for two free leagues, ~95 days of form, today & next day.

    One date-range URL, paginated. Never accept unrequested leagues or incomplete
    pages as a complete feed; on error keep other providers operating normally.
    """
    diagnostics = {'state': 'not_configured', 'matches': 0, 'finished': 0,
                   'upcoming': 0, 'pages': 0, 'error': None}
    if not token:
        return [], diagnostics
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    if request is None:
        request = fetch_page
    start = target_date - timedelta(days=94)
    end = target_date + timedelta(days=2)
    base = f'{BASE}/fixtures/between/{start.isoformat()}/{end.isoformat()}'
    rows = {}
    try:
        for page in range(1, max_pages + 1):
            query = urlencode({'include': 'participants;scores', 'per_page': 50,
                               'page': page, 'order': 'desc'})
            payload = request(base + '?' + query, token)
            if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
                raise ValueError('Unexpected page format')
            for item in payload['data']:
                fixture = normalize(item, now)
                if fixture is not None:
                    rows[fixture['id']] = fixture
            diagnostics['pages'] = page
            paging = payload.get('pagination') or {}
            if not isinstance(paging, dict):
                raise ValueError('Unexpected pagination')
            if paging.get('has_more') is not True:
                break
        else:
            raise ValueError('Sportmonks pagination limit exceeded')
    except Exception as exc:
        # Do not put exception text in logs: request/provider errors may expose
        # sensitive credentials or account metadata.
        diagnostics['state'] = 'unavailable'
        diagnostics['error'] = type(exc).__name__
        return [], diagnostics
    fixtures = list(rows.values())
    diagnostics['state'] = 'ok'
    diagnostics['matches'] = len(fixtures)
    diagnostics['finished'] = sum(m['status'] == 'FINISHED' for m in fixtures)
    diagnostics['upcoming'] = sum(m['status'] == 'SCHEDULED' and
                                  datetime.fromisoformat(m['utcDate']).astimezone(OSLO).date() == target_date
                                  for m in fixtures)
    return fixtures, diagnostics


def results_for(identifiers, token: str, *, request=None) -> list[dict]:
    """Settle only exact saved Sportmonks IDs with confirmed finished results.

    One multi-ID request per 20 unique IDs, rather than per match.
    """
    if not token:
        return []
    if request is None:
        request = fetch_page
    ids = sorted({int(x[len('sm-match:'):]) for x in identifiers
                  if isinstance(x, str) and x.startswith('sm-match:')
                  and x[len('sm-match:'):].isdigit() and int(x[len('sm-match:'):]) > 0})
    completed = []
    now = datetime.now(timezone.utc)
    for start in range(0, len(ids), 20):
        selected = ids[start:start + 20]
        url = BASE + '/fixtures/multi/' + ','.join(map(str, selected)) + '?' + urlencode({
            'include': 'participants;scores'})
        response = request(url, token)
        if not isinstance(response, dict) or not isinstance(response.get('data'), list):
            raise ValueError('Unexpected Sportmonks results response')
        for item in response['data']:
            if not isinstance(item, dict) or item.get('id') not in selected:
                continue
            fixture = normalize(item, now)
            if fixture and fixture['status'] == 'FINISHED':
                completed.append(fixture)
    return completed
