"""Choose supported bookmaker leagues with real games on the target Oslo day.

The Odds API sports and event discovery routes do not consume odds credits.
No actual bookmaker odds or model probabilities are generated here.
"""
from __future__ import annotations
from datetime import date, datetime
from urllib.parse import quote, urlencode
from international_v43 import INTERNATIONAL_KEYS, available_on_day
from odds_first_v25 import COMPETITIONS

NATIONS_LEAGUE = 'soccer_uefa_nations_league'


def discover_matchday_sports(odds_key: str, target_day: date, now: datetime,
                             fetch, base: str, known_sports: list[str] | None = None,
                             *, max_sports: int = 4):
    """Only request paid bookmaker prices for leagues having real fixtures.

    Catalog lookup failure may fall back to separately verified official fixtures.
    Per-league event errors are not used as evidence unless a separate official
    fixture feed already verified that league has a game on this day.
    """
    known = list(dict.fromkeys(
        sport for sport in (known_sports or []) if sport in COMPETITIONS))
    diagnostic = {'targetDate': target_day.isoformat(), 'catalogAvailable': False,
                  'matchesBySport': {}, 'selected': [], 'errors': []}
    if not odds_key or max_sports <= 0:
        return [], diagnostic

    try:
        catalog = fetch(base + '/sports/?' + urlencode({'apiKey': odds_key}))
        if not isinstance(catalog, list):
            raise ValueError('Unexpected sports catalog')
        active = {row.get('key') for row in catalog if isinstance(row, dict)
                  and row.get('key') in COMPETITIONS and row.get('active') is not False}
        diagnostic['catalogAvailable'] = True
    except (OSError, TimeoutError, ValueError, TypeError, RuntimeError):
        diagnostic['errors'].append('Sports catalog temporarily unavailable')
        diagnostic['selected'] = known[:max_sports]
        return diagnostic['selected'], diagnostic

    counts = {}
    failed = set()
    for sport in COMPETITIONS:
        if sport not in active:
            continue
        try:
            url = base + '/sports/' + quote(sport, safe='') + '/events?' + urlencode({'apiKey': odds_key})
            events = fetch(url)
            if not isinstance(events, list):
                raise ValueError('Unexpected event list')
            count = available_on_day(events, target_day, now)
            if count:
                counts[sport] = count
        except (OSError, TimeoutError, ValueError, TypeError, RuntimeError):
            failed.add(sport)
            diagnostic['errors'].append('Events unavailable for ' + sport)

    for sport in known:
        if sport in active and sport in failed:
            counts.setdefault(sport, 1)

    rank = {sport: index for index, sport in enumerate(known)}
    def priority(sport):
        if sport == NATIONS_LEAGUE:
            return (0, 0, -counts[sport], sport)
        if sport in known:
            return (1, rank[sport], -counts[sport], sport)
        if sport in INTERNATIONAL_KEYS:
            return (2, 0, -counts[sport], sport)
        return (3, 0, -counts[sport], sport)

    selected = sorted(counts, key=priority)[:max_sports]
    diagnostic['matchesBySport'] = counts
    diagnostic['selected'] = selected
    return selected, diagnostic
