"""Check Nations League bookmaker events against UEFA's match calendar."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from urllib.parse import urlencode

from matchday_sports_v44 import NATIONS_LEAGUE
from national_form_v48 import OSLO, team_identity
from odds_first_v25 import parse_kickoff

CALENDAR_URL = 'https://match.uefa.com/v5/matches'
MATCH_LIMIT = 100
KICKOFF_TOLERANCE = timedelta(hours=1)


def official_kickoffs(day, fetch):
    query = urlencode({
        'competitionId': '2014', 'seasonYear': day.year + (day.month >= 7),
        'fromDate': (day - timedelta(days=1)).isoformat(),
        'toDate': (day + timedelta(days=1)).isoformat(),
        'order': 'ASC', 'limit': MATCH_LIMIT, 'offset': 0,
    })
    rows = fetch(f'{CALENDAR_URL}?{query}')
    if not isinstance(rows, list) or len(rows) >= MATCH_LIMIT:
        raise ValueError('Invalid or incomplete UEFA calendar')

    kickoffs = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid UEFA fixture')
        if row.get('status') in {'CANCELLED', 'POSTPONED', 'ABANDONED'}:
            continue
        kickoff = parse_kickoff((row.get('kickOffTime') or {}).get('dateTime'))
        if kickoff is None:
            raise ValueError('Missing UEFA kickoff')
        if kickoff.astimezone(OSLO).date() != day:
            continue
        home = team_identity((row.get('homeTeam') or {}).get('teamCode'))
        away = team_identity((row.get('awayTeam') or {}).get('teamCode'))
        if not home or not away or home == away:
            raise ValueError('Missing or invalid UEFA team codes')
        kickoffs[home, away].append(kickoff)
    return kickoffs


def verify_events(events, day, fetch):
    """Drop unverified fixtures, and withhold conflicting listings during UEFA outages."""
    nations_league_events = {}
    for index, event in enumerate(events):
        if not isinstance(event, dict) or event.get('sport_key') != NATIONS_LEAGUE:
            continue
        kickoff = parse_kickoff(event.get('commence_time'))
        if kickoff is not None and kickoff.astimezone(OSLO).date() == day:
            pair = (team_identity(event.get('home_team')), team_identity(event.get('away_team')))
            nations_league_events[index] = (pair, kickoff)
    if not nations_league_events:
        return events, None

    try:
        kickoffs = official_kickoffs(day, fetch)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        opponents = defaultdict(set)
        for (home, away), _ in nations_league_events.values():
            if home and away and home != away:
                opponents[home].add(away)
                opponents[away].add(home)
        keep = {index for index, ((home, away), _) in nations_league_events.items()
                if len(opponents[home]) == len(opponents[away]) == 1 and home != away}
        status = {'state': 'unavailable', 'error': type(exc).__name__}
    else:
        keep = {index for index, (pair, kickoff) in nations_league_events.items()
                if any(abs(kickoff - official) <= KICKOFF_TOLERANCE
                       for official in kickoffs.get(pair, ()))}
        status = {'state': 'checked'}
    dropped = set(nations_league_events) - keep
    status['excluded'] = len(dropped)
    return [event for index, event in enumerate(events) if index not in dropped], status
