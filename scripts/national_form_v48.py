"""Independent history for senior national-team fixtures.

The CC0 international_results CSV has dates but no kickoff times or
regulation-time scores for games with extra time. Import only known
regulation-time competitions and use completed dates before the analysis.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from form_history_v38 import verified_form_records
from international_v43 import INTERNATIONAL_KEYS
from odds_first_v25 import COMPETITIONS

OSLO = ZoneInfo('Europe/Oslo')
SOURCE = 'International football results (Mart Jürisoo)'
RESULTS_URL = 'https://raw.githubusercontent.com/martj42/international_results/master/results.csv'
HISTORY_DAYS = 548
HALF_LIFE_DAYS = 270
FRIENDLY_WEIGHT = 0.70
MAX_BYTES = 8_000_000
COMPETITION_CODES = {COMPETITIONS[sport][0] for sport in INTERNATIONAL_KEYS} | {
    'UNL', 'WC', 'EC', 'ECQ', 'WCQ',
}
REQUIRED_COLUMNS = {'date', 'home_team', 'away_team', 'home_score', 'away_score', 'tournament', 'neutral'}

# UEFA association codes and exact provider aliases. All other senior teams
# are joined only by an exact, accent-normalized name in the CSV.
UEFA = {
    'ALB': ('Albania',), 'AND': ('Andorra',), 'ARM': ('Armenia',),
    'AUT': ('Austria',), 'AZE': ('Azerbaijan',), 'BLR': ('Belarus',),
    'BEL': ('Belgium',), 'BIH': ('Bosnia and Herzegovina', 'Bosnia-Herzegovina'),
    'BUL': ('Bulgaria',), 'CRO': ('Croatia',), 'CYP': ('Cyprus',),
    'CZE': ('Czechia', 'Czech Republic'), 'DEN': ('Denmark',), 'ENG': ('England',),
    'EST': ('Estonia',), 'FRO': ('Faroe Islands',), 'FIN': ('Finland',),
    'FRA': ('France',), 'GEO': ('Georgia',), 'GER': ('Germany',), 'GIB': ('Gibraltar',),
    'GRE': ('Greece',), 'HUN': ('Hungary',), 'ISL': ('Iceland',),
    'IRL': ('Republic of Ireland', 'Ireland'), 'ISR': ('Israel',), 'ITA': ('Italy',),
    'KAZ': ('Kazakhstan',), 'KOS': ('Kosovo',), 'LVA': ('Latvia',),
    'LIE': ('Liechtenstein',), 'LTU': ('Lithuania',), 'LUX': ('Luxembourg',),
    'MLT': ('Malta',), 'MDA': ('Moldova',), 'MNE': ('Montenegro',),
    'NED': ('Netherlands',), 'MKD': ('North Macedonia',),
    'NIR': ('Northern Ireland',), 'NOR': ('Norway',), 'POL': ('Poland',),
    'POR': ('Portugal',), 'ROU': ('Romania',), 'RUS': ('Russia',),
    'SMR': ('San Marino',), 'SCO': ('Scotland',), 'SRB': ('Serbia',),
    'SVK': ('Slovakia',), 'SVN': ('Slovenia',), 'ESP': ('Spain',),
    'SWE': ('Sweden',), 'SUI': ('Switzerland',), 'TUR': ('Türkiye', 'Turkey'),
    'UKR': ('Ukraine',), 'WAL': ('Wales',),
}


def _name_key(name):
    normalized = unicodedata.normalize('NFKD', str(name or '').casefold())
    return re.sub(r'[^a-z0-9]+', '', normalized)


_UEFA_CODES = {_name_key(name): code for code, names in UEFA.items() for name in (*names, code)}
_NAME_ALIASES = {
    'korearepublic': 'southkorea', 'republicofkorea': 'southkorea',
    'iriran': 'iran', 'unitedstatesofamerica': 'unitedstates', 'usa': 'unitedstates',
    'caboverde': 'capeverde', 'ivorycoast': 'cotedivoire',
    'congodr': 'drcongo', 'democraticrepublicofthecongo': 'drcongo',
}


def team_identity(name):
    key = _name_key(name)
    if not key:
        return None
    if key in _UEFA_CODES:
        return 'national:' + _UEFA_CODES[key]
    return 'national-name:' + _NAME_ALIASES.get(key, key)


def is_national_fixture(fixture):
    return (fixture.get('competition') or {}).get('code') in COMPETITION_CODES


def regular_time_competition(day, competition, home, away):
    """A positive result requires a competition phase with no extra time."""
    both_uefa = all(team.startswith('national:') for team in (home, away))
    if competition == 'Friendly':
        return True
    if competition == 'UEFA Nations League':
        return both_uefa and (
            day.year % 2 == 0 and day.month in (9, 10, 11)
            or day.year == 2022 and day.month == 6
        )
    if competition == 'FIFA World Cup qualification':
        # UEFA's 2026 group matches ran Mar–Nov 2025. The March 2026
        # single-leg play-offs could include extra time.
        return both_uefa and date(2025, 3, 21) <= day <= date(2025, 11, 18)
    if competition == 'FIFA World Cup':
        return date(2026, 6, 11) <= day <= date(2026, 6, 27)
    return False


def parse_results(csv_text, first_day, before_day):
    reader = csv.DictReader(io.StringIO(csv_text))
    if not REQUIRED_COLUMNS.issubset(reader.fieldnames or []):
        raise ValueError('Unexpected international results columns')
    results, conflicts = {}, set()
    for row in reader:
        try:
            day = date.fromisoformat(row['date'])
            if not first_day <= day < before_day:
                continue
            home_name = row['home_team'].strip()
            away_name = row['away_team'].strip()
            if not (2 <= len(home_name) <= 100 and 2 <= len(away_name) <= 100):
                continue
            home, away = team_identity(home_name), team_identity(away_name)
            if not home or not away or home == away:
                continue
            competition = row['tournament']
            if not regular_time_competition(day, competition, home, away):
                continue
            hg, ag = int(row['home_score']), int(row['away_score'])
            neutral = row['neutral'].strip().upper()
            if not (0 <= hg <= 30 and 0 <= ag <= 30 and neutral in ('TRUE', 'FALSE')):
                continue
        except (AttributeError, TypeError, ValueError):
            continue
        key = (day, *sorted((home, away)))
        match = {
            'id': f'national-match:{day}:{home}:{away}',
            # A date anchor for the existing form reader. The actual time is unknown.
            'utcDate': datetime.combine(day, time.min, OSLO).isoformat(),
            'status': 'FINISHED', 'formSource': SOURCE, 'dateOnly': True,
            'neutralVenue': neutral == 'TRUE',
            'homeTeam': {'id': home, 'name': home_name},
            'awayTeam': {'id': away, 'name': away_name},
            'competition': {'name': competition},
            'score': {'fullTime': {'home': hg, 'away': ag}, 'duration': 'REGULAR'},
        }
        previous = results.setdefault(key, match)
        if any(previous[field] != match[field] for field in ('id', 'score', 'neutralVenue')):
            conflicts.add(key)
    return [match for key, match in results.items() if key not in conflicts]


def fetch_results_csv():
    request = Request(RESULTS_URL, headers={'User-Agent': 'OddsGeneratoren3000/4.8'})
    with urlopen(request, timeout=20) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('International results file is too large')
    return raw.decode('utf-8-sig')


def load_history(now, *, fetch=fetch_results_csv):
    cutoff = now.astimezone(OSLO).date()
    try:
        rows = parse_results(fetch(), cutoff - timedelta(days=HISTORY_DAYS), cutoff)
    except (OSError, ValueError) as exc:
        return [], {'state': 'unavailable', 'error': type(exc).__name__}
    return rows, {
        'state': 'ok' if rows else 'empty',
        'source': SOURCE,
        'matches': len(rows),
        'latestResultDate': max((row['utcDate'][:10] for row in rows), default=None),
    }


def form_records(history, team, before, *, days=HISTORY_DAYS):
    # Do not use same-day records when the source provides no kickoff time.
    cutoff = before.astimezone(OSLO).replace(hour=0, minute=0, second=0, microsecond=0)
    identity = team_identity(team.get('name') or team.get('shortName'))
    return verified_form_records(history, identity, cutoff, days=days, limit=24)


def form_weights(records, before, *, half_life=HALF_LIFE_DAYS):
    day = before.astimezone(OSLO).date()
    return [
        0.5 ** (max(0, (day - date.fromisoformat(record['localDate'])).days) / half_life)
        * (FRIENDLY_WEIGHT if record['competition'] == 'Friendly' else 1)
        for record in records
    ]
