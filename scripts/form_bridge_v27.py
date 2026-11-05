"""Bridge verified domestic league results to bookmaker-discovered UEFA fixtures.

Only completed football-data.org match results are used. Names are checked on
both sides and ambiguous mappings are rejected. Never infer historical scores.
This does not imply the model is backtested or a betting edge is established.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
import re
import unicodedata

# These competitions are available through football-data.org's free tier.
FREE_COMPETITIONS = ('PL', 'PD', 'BL1', 'SA', 'FL1', 'PPL', 'DED', 'ELC')

# Curated club aliases, not general fuzzy guesses: all variants refer to the
# same club. Other names must pass the strict identity/margin check.
CLUB_ALIASES = {
    'olympique lyonnais': 'lyon',
    'olympique lyon': 'lyon',
    'olympique de marseille': 'marseille',
    'olympique marseille': 'marseille',
    'real sociedad de futbol': 'real sociedad',
    'real sociedad': 'real sociedad',
    'bayer 04 leverkusen': 'bayer leverkusen',
    'bayer leverkusen': 'bayer leverkusen',
    'atletico de madrid': 'atletico madrid',
    'atletico madrid': 'atletico madrid',
    'fc internazionale milano': 'internazionale',
    'internazionale milano': 'internazionale',
    'internazionale': 'internazionale',
    'inter milan': 'internazionale',
    'sporting clube de portugal': 'sporting lisbon',
    'sporting cp': 'sporting lisbon',
    'sporting lisbon': 'sporting lisbon',
}


def canonical_name(value: str) -> str:
    s = unicodedata.normalize('NFKD', str(value or '').casefold())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    return CLUB_ALIASES.get(s, s)


def valid_finished(m: dict, before: datetime) -> bool:
    if not isinstance(m, dict) or m.get('status') != 'FINISHED':
        return False
    try:
        d = datetime.fromisoformat(str(m['utcDate']).replace('Z', '+00:00'))
    except (KeyError, TypeError, ValueError):
        return False
    if d.tzinfo is None or d.astimezone(timezone.utc) >= before:
        return False
    h, a = (m.get('homeTeam') or {}), (m.get('awayTeam') or {})
    score = (m.get('score') or {}).get('fullTime') or {}
    return (h.get('id') is not None and a.get('id') is not None and
            h['id'] != a['id'] and type(score.get('home')) is int and
            type(score.get('away')) is int and
            min(score['home'], score['away']) >= 0)


def load_free_history(fetch, base: str, target_date: date, *, leagues=FREE_COMPETITIONS) -> tuple[list, list]:
    """Fetch scored matches, with the caller's rate-limited authorized client.

    Any denied competition is skipped, not confused with a zero-goal game.
    """
    start = (target_date - timedelta(days=165)).isoformat()
    ending = target_date.isoformat()
    by_id, issues = {}, []
    for code in leagues:
        url = base + f'/competitions/{code}/matches?' + urlencode({
            'dateFrom': start, 'dateTo': ending, 'status': 'FINISHED', 'limit': 500})
        try:
            payload = fetch(url)
            rows = payload.get('matches') if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise ValueError('Missing results list')
            for m in rows:
                if isinstance(m, dict) and m.get('id') is not None:
                    by_id[str(m['id'])] = m
        except (OSError, ValueError, TypeError, TimeoutError) as exc:
            issues.append(f'Formhistorikk {code}: {type(exc).__name__}')
    return list(by_id.values()), issues


def bridge(fixtures: list, historical: list, now: datetime, score_fn) -> tuple[list, dict]:
    """Attach official team IDs and completed results to bookmaker-only fixtures.

    score_fn compares football club names in the existing project's language.
    A team must have at least three completed matches and an unambiguous
    identity before its form can be used. The subsequent quality gate still
    requires more evidence before a recommendation is allowed.
    """
    if now.tzinfo is None:
        raise ValueError('now must have a timezone')
    unique_history = {}
    clubs = defaultdict(lambda: {'names': set(), 'games': 0})
    for m in historical:
        if not valid_finished(m, now):
            continue
        unique_history[str(m['id'])] = m
    for m in unique_history.values():
        for side in ('homeTeam', 'awayTeam'):
            t = m[side]
            c = clubs[t['id']]
            c['games'] += 1
            for key in ('name', 'shortName'):
                name = t.get(key)
                if isinstance(name, str) and name.strip():
                    c['names'].add(name)

    def identify(raw: dict):
        aliases = [raw.get('name'), raw.get('shortName')]
        aliases = [x for x in aliases if isinstance(x, str) and x.strip()]
        if not aliases:
            return None
        found = []
        for team_id, club in clubs.items():
            if club['games'] < 3:
                continue
            score = max((1.0 if canonical_name(a) == canonical_name(b)
                         else float(score_fn(a, b)) for a in aliases
                         for b in club['names']), default=0.0)
            if score >= 0.87:
                found.append((score, club['games'], str(team_id), team_id))
        found.sort(reverse=True)
        if not found:
            return None
        if len(found) > 1 and found[0][0] - found[1][0] < .08:
            return None
        return found[0][3]

    existing = {str(m.get('id')):m for m in fixtures if isinstance(m, dict) and m.get('id') is not None}
    matched = 0
    matches_with_both = 0
    for m in fixtures:
        if not isinstance(m, dict) or not str(m.get('id', '')).startswith('odds:'):
            continue
        home = m.get('homeTeam') or {}
        away = m.get('awayTeam') or {}
        a, b = identify(home), identify(away)
        if a is not None and b is not None and a == b:
            # Never assign both sides of a fixture to the same club.
            continue
        if a is not None:
            home['id'] = a
            matched += 1
        if b is not None:
            away['id'] = b
            matched += 1
        if a is not None or b is not None:
            m['formSource'] = 'football-data.org: completed domestic fixtures'
        if a is not None and b is not None:
            matches_with_both += 1
    for event_id, m in unique_history.items():
        existing.setdefault(event_id, m)
    return list(existing.values()), {
        'historyFixturesAvailable': len(unique_history),
        'matchedOddsTeams': matched,
        'oddsFixturesWithBothTeamsMatched': matches_with_both,
    }
