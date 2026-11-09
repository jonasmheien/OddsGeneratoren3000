"""Quota-safe international-football fixture discovery for OddsGeneratoren3000.

Only real, bookmaker-listed international events on the *target Oslo day* are
eligible. This module never generates odds, scores, form or betting predictions.

The Odds API v4's /sports and /sports/{sport}/events endpoints do not spend
odds quota. Any paid odds requests still go through the existing daily builder
and the existing remaining-credit reserve.
"""
from __future__ import annotations

from datetime import datetime, date, timezone
from urllib.parse import urlencode, quote
from zoneinfo import ZoneInfo

OSLO = ZoneInfo('Europe/Oslo')
# Official The Odds API v4 sport keys. Friendlies are intentionally omitted:
# there is no documented stable general friendlies key in the supplier catalog.
INTERNATIONAL = (
    ('soccer_uefa_nations_league', 'UEFA Nations League'),
    ('soccer_fifa_world_cup_qualifiers_europe', 'VM-kvalifisering Europa'),
    ('soccer_fifa_world_cup_qualifiers_south_america', 'VM-kvalifisering Sør-Amerika'),
    ('soccer_uefa_euro_qualification', 'EM-kvalifisering'),
    ('soccer_fifa_world_cup', 'FIFA World Cup'),
    ('soccer_uefa_european_championship', 'EM'),
)
INTERNATIONAL_KEYS = frozenset(k for k, _ in INTERNATIONAL)


def _kickoff(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def available_on_day(events, target_day: date, now: datetime) -> int:
    """Count only valid, independent scheduled national-team fixtures."""
    if now.tzinfo is None:
        raise ValueError('Current time must be timezone aware')
    if not isinstance(events, list):
        return 0
    seen = set()
    for item in events:
        if not isinstance(item, dict):
            continue
        kickoff = _kickoff(item.get('commence_time'))
        home = str(item.get('home_team') or '').strip()
        away = str(item.get('away_team') or '').strip()
        if (kickoff is None or kickoff <= now or kickoff.astimezone(OSLO).date() != target_day
                or not home or not away or home.casefold() == away.casefold()):
            continue
        # A malformed event must not influence bookmaker quota allocation.
        event_id = item.get('id')
        if not isinstance(event_id, str) or len(event_id) < 8:
            continue
        seen.add(event_id)
    return len(seen)


def discover_international(odds_key: str, target_day: date, now: datetime,
                           fetch, base: str, *, max_sports: int = 2):
    """Discover up to max_sports active international competitions (no paid odds).

    Returns sport keys and public, non-sensitive diagnostics. Any discovery
    failure is non-fatal; the existing domestic analysis remains intact.
    """
    diagnostics = {'targetDate': target_day.isoformat(), 'catalogAvailable': False,
                   'activeCompetitions': [], 'fixturesByCompetition': {},
                   'selected': [], 'errors': []}
    if not odds_key or max_sports < 1:
        return [], diagnostics
    try:
        catalog = fetch(base + '/sports/?' + urlencode({'apiKey': odds_key}))
        if not isinstance(catalog, list):
            raise ValueError('Unexpected sports catalog format')
        active = {x['key'] for x in catalog if isinstance(x, dict)
                  and x.get('key') in INTERNATIONAL_KEYS and x.get('active') is not False}
        diagnostics['catalogAvailable'] = True
    except (OSError, TimeoutError, ValueError, TypeError, RuntimeError):
        diagnostics['errors'].append('Sports catalog unavailable')
        return [], diagnostics
    diagnostics['activeCompetitions'] = [k for k, _ in INTERNATIONAL if k in active]
    counts = {}
    for sport, _ in INTERNATIONAL:
        if sport not in active:
            continue
        try:
            url = base + '/sports/' + quote(sport, safe='') + '/events?' + urlencode({'apiKey': odds_key})
            events = fetch(url)
            if not isinstance(events, list):
                raise ValueError('Unexpected event list format')
            count = available_on_day(events, target_day, now)
            if count:
                counts[sport] = count
        except (OSError, TimeoutError, ValueError, TypeError, RuntimeError):
            # Do not print upstream errors: an API client exception may contain
            # the full request URL, including its private token.
            diagnostics['errors'].append('Events temporarily unavailable for ' + sport)
    diagnostics['fixturesByCompetition'] = counts
    # Nations League first, then genuine volume on the target date. Never pay
    # for a competition solely because it appears in a static list.
    priority = {key: index for index, (key, _) in enumerate(INTERNATIONAL)}
    selected = sorted(counts, key=lambda k: (0 if k == 'soccer_uefa_nations_league' else 1,
                                               -counts[k], priority[k]))[:max_sports]
    diagnostics['selected'] = selected
    return selected, diagnostics


def prioritize_sports(domestic: list[str], international: list[str], limit: int) -> list[str]:
    """Reserve slots for observed internationals without losing all club coverage."""
    if limit <= 0:
        return []
    result = []
    for key in list(international) + list(domestic):
        if isinstance(key, str) and key not in result:
            result.append(key)
        if len(result) >= max(0, limit):
            break
    return result
