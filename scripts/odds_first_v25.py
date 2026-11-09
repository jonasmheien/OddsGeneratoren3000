"""Evidence-only bookmaker fixture discovery for next-day preview.

The Odds API returns genuine upcoming bookmaker event listings. They may fill
fixture discovery gaps, but have *no* independent form or result history.
A bookmaker listing must therefore NEVER be treated as a trained forecast or
used to synthesize past scores.
"""
from __future__ import annotations

import re
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

OSLO = ZoneInfo('Europe/Oslo')
PREVIEW_SPORTS = (
    'soccer_uefa_europa_league',
    'soccer_uefa_europa_conference_league',
)
COMPETITIONS = {
    # International national-team tournaments. Fixture discovery and market quotes
    # come only from the real supplier; no model/form is fabricated.
    'soccer_uefa_nations_league': ('ODDS-UNL', 'UEFA Nations League'),
    'soccer_fifa_world_cup_qualifiers_europe': ('ODDS-WCQ-EUR', 'VM-kvalifisering Europa'),
    'soccer_fifa_world_cup_qualifiers_south_america': ('ODDS-WCQ-SAM', 'VM-kvalifisering Sør-Amerika'),
    'soccer_uefa_euro_qualification': ('ODDS-EUROQ', 'EM-kvalifisering'),
    'soccer_fifa_world_cup': ('ODDS-WC', 'FIFA World Cup'),
    'soccer_uefa_european_championship': ('ODDS-EURO', 'UEFA European Championship'),
    'soccer_uefa_europa_league': ('ODDS-EL', 'UEFA Europa League'),
    'soccer_uefa_europa_conference_league': ('ODDS-ECL', 'UEFA Conference League'),
    'soccer_epl': ('ODDS-PL', 'Premier League'),
    'soccer_efl_champ': ('ODDS-ELC', 'Championship'),
    'soccer_italy_serie_a': ('ODDS-SA', 'Serie A'),
    'soccer_germany_bundesliga': ('ODDS-BL1', 'Bundesliga'),
    'soccer_spain_la_liga': ('ODDS-PD', 'La Liga'),
    'soccer_france_ligue_one': ('ODDS-FL1', 'Ligue 1'),
    'soccer_netherlands_eredivisie': ('ODDS-DED', 'Eredivisie'),
    'soccer_portugal_primeira_liga': ('ODDS-PPL', 'Primeira Liga'),
    'soccer_uefa_champs_league': ('ODDS-CL', 'UEFA Champions League'),
    'soccer_norway_eliteserien': ('ODDS-NOR', 'Eliteserien'),
    'soccer_sweden_allsvenskan': ('ODDS-SWE', 'Allsvenskan'),
    'soccer_sweden_superettan': ('ODDS-SE2', 'Superettan'),
    'soccer_denmark_superliga': ('ODDS-DNK', 'Superliga'),
    'soccer_spain_segunda_division': ('ODDS-SP2', 'La Liga 2'),
}


def preview_sports(selected: list[str], *, max_sports: int = 2) -> list[str]:
    """Use genuine expected European competitions when fixture discovery is empty.

    This fallback applies to explicit next-day preview only; daily snapshots
    retain their existing API budget and regular fixture results collection.
    """
    unique = []
    for sport in (selected or []) + list(PREVIEW_SPORTS):
        if sport and sport not in unique:
            unique.append(sport)
    return unique[:max(0, max_sports)]


def _utc(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _team_name(value):
    if not isinstance(value, str):
        return ''
    # Avoid bogus, giant labels in published HTML and unstable identity keys.
    value = ' '.join(value.split())
    return value if 1 < len(value) <= 100 else ''


def _normalized(value):
    return re.sub(r'[^a-z0-9]+', '', value.casefold())


def _fixture_team_key(value):
    """Only verified, narrow aliases for the same club in fixture matching."""
    name = _normalized(value)
    return {'boltonwanderers': 'bolton',
            'silkeborgif': 'silkeborg'}.get(name, name)


def _quoted(event):
    """Require observed valid numerical prices, not just an empty bookmaker ID."""
    for bookmaker in event.get('bookmakers') or []:
        if not isinstance(bookmaker, dict):
            continue
        for market in bookmaker.get('markets') or []:
            if not isinstance(market, dict) or market.get('key') not in ('h2h', 'totals'):
                continue
            for outcome in market.get('outcomes') or []:
                if not isinstance(outcome, dict):
                    continue
                price = outcome.get('price')
                if type(price) in (int, float) and 1.01 < price < 100:
                    return True
    return False


def _already_listed(name_home, name_away, kickoff, existing):
    """Deduplicate exact two-sided team matches with nearby kickoff time.

    Deliberately avoid fuzzy single-team matching: uncertain sources are kept
    separately and never get odds attached to the wrong fixture.
    """
    home, away = _fixture_team_key(name_home), _fixture_team_key(name_away)
    for item in existing:
        h = item.get('homeTeam') or {}
        a = item.get('awayTeam') or {}
        h_names = [h.get('name'), h.get('shortName')]
        a_names = [a.get('name'), a.get('shortName')]
        if home not in {_fixture_team_key(x) for x in h_names if isinstance(x, str)}:
            continue
        if away not in {_fixture_team_key(x) for x in a_names if isinstance(x, str)}:
            continue
        current = _utc(item.get('utcDate'))
        if current is not None and abs((current - kickoff).total_seconds()) <= 3600:
            return True
    return False


def fixtures_from_quotes(events: list, now: datetime, target_date: date,
                         existing: list | None = None) -> list[dict]:
    """Build true upcoming event entries from bookmaker quotes.

    These fixtures intentionally contain no model, fake goals, team history or
    predicted outcomes; the qualification gate will reject them without data.
    """
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    known = list(existing or [])
    created = []
    seen_ids = set()
    for event in events or []:
        if not isinstance(event, dict):
            continue
        sport = event.get('sport_key')
        if sport not in COMPETITIONS:
            continue
        kickoff = _utc(event.get('commence_time'))
        if kickoff is None or kickoff <= now or kickoff.astimezone(OSLO).date() != target_date:
            continue
        home, away = _team_name(event.get('home_team')), _team_name(event.get('away_team'))
        if not home or not away or _normalized(home) == _normalized(away):
            continue
        event_id = event.get('id')
        if not isinstance(event_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,96}', event_id):
            continue
        if not _quoted(event):
            continue
        if event_id in seen_ids or _already_listed(home, away, kickoff, known):
            continue
        seen_ids.add(event_id)
        code, title = COMPETITIONS[sport]
        fixture = {
            'id': 'odds:' + event_id,
            'utcDate': kickoff.isoformat(),
            'status': 'SCHEDULED',
            'homeTeam': {'id': 'odds-home:' + event_id, 'name': home, 'shortName': home, 'crest': None},
            'awayTeam': {'id': 'odds-away:' + event_id, 'name': away, 'shortName': away, 'crest': None},
            'competition': {'code': code, 'name': title, 'emblem': None},
            'score': {'fullTime': {'home': None, 'away': None}},
            'fixtureSource': 'The Odds API bookmaker listing',
            'formSource': None,
        }
        created.append(fixture)
        known.append(fixture)
    return sorted(created, key=lambda x: x['utcDate'])
