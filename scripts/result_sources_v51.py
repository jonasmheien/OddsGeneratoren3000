"""Match saved bookmaker IDs to explicit results from independent fixture feeds.

Both teams and the kickoff must match. No fuzzy names, guessed scores, or
bookmaker-credit requests. Missing or conflicting results remain unverified.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from urllib.parse import urlencode

from final_selection_v40 import club, dt, OSLO
from form_bridge_v27 import canonical_name
from national_form_v48 import team_identity
from nations_league_fixtures import CALENDAR_URL, MATCH_LIMIT

UEFA_COMPETITIONS = {'UEFA Nations League': '2014',
                     'UEFA Champions League': '1', 'Champions League': '1',
                     'UEFA Europa League': '14', 'Europa League': '14',
                     'UEFA Conference League': '2019', 'Conference League': '2019'}


def uefa_competition(pick):
    return UEFA_COMPETITIONS.get(pick.get('league'))


def national(pick):
    return pick.get('league') == 'UEFA Nations League' or pick.get('leagueCode') in ('UNL', 'ODDS-UNL')


def team_key(name, is_national=False):
    return team_identity(name) if is_national else club(canonical_name(name))


# Explicit senior-team aliases. Publication keys above stay immutable. Do not
# strip arbitrary prefixes/suffixes: Ajax, Jong Ajax and Ajax U19 differ.
CLUB_ALIASES = (
    ('Bayer Leverkusen', 'Bayer 04 Leverkusen', 'Leverkusen'),
    ('Dinamo Zagreb', 'GNK Dinamo', 'GNK Dinamo Zagreb'),
    ('Celta Vigo', 'RC Celta de Vigo', 'Celta'),
    ('Union Saint-Gilloise', 'Royale Union Saint-Gilloise', 'Union SG'),
    ('Besiktas JK', 'Beşiktaş', 'Beşiktaş JK'),
    ('FC Ararat-Armenia', 'Ararat-Armenia'),
    ('Hapoel Be’er Sheva', 'Hapoel Beer Sheva', 'H. Beer-Sheva'),
    ('Panathinaikos FC', 'Panathinaikos'),
    ('PFC CSKA Sofia', 'CSKA Sofia'),
    ('Universitatea Craiova', 'CS Universitatea Craiova', 'Univ. Craiova'),
    ('KF Egnatia', 'Egnatia'),
    ('FC Twente Enschede', 'FC Twente', 'Twente'),
    ('Pafos FC', 'Pafos'),
    ('FC Copenhagen', 'FC København', 'Copenhagen'),
    ('FC Iberia 1999', 'Iberia Tbilisi'),
    ('FC Lugano', 'Lugano'),
    ('FK Kauno Žalgiris', 'Kauno Žalgiris'),
    ('AS Monaco', 'AS Monaco FC', 'Monaco'),
    ('FC Nordsjaelland', 'FC Nordsjælland', 'Nordsjælland'),
    ('Brighton and Hove Albion', 'Brighton & Hove Albion FC', 'Brighton'),
    ('Manchester United', 'Manchester United FC'),
    ('Bayern Munich', 'FC Bayern München', 'Bayern München'),
    ('FSV Mainz 05', '1. FSV Mainz 05', 'Mainz 05'),
    ('Paris Saint Germain', 'Paris Saint-Germain FC', 'Paris Saint-Germain'),
    ('Troyes', 'ES Troyes AC'),
    ('AZ Alkmaar', 'AZ'),
    ('Groningen', 'FC Groningen'),
    ('PSV Eindhoven', 'PSV'),
    ('Ajax', 'AFC Ajax'),
    ('SC Cambuur', 'SC Cambuur-Leeuwarden'),
    ('NEC Nijmegen', 'N.E.C.', 'Nijmegen Eendracht Combinatie'),
    ('Rennes', 'Stade Rennais FC'),
    ('Lille', 'Lille OSC'),
    ('CF Estrela', 'CF Estrela da Amadora'),
    ('Benfica', 'SL Benfica'),
    ('Levante', 'Levante UD'),
    ('Venezia', 'Venezia FC'),
    ('Udinese', 'Udinese Calcio'),
)
_RESULT_KEYS = {team_key(alias): team_key(group[0]) for group in CLUB_ALIASES for alias in group}


def result_team_key(name, is_national=False):
    key = team_key(name, is_national)
    return key if is_national else _RESULT_KEYS.get(key, key)


def selection_key(pick):
    kickoff = dt(pick.get('kickoff'))
    home, away = (team_key(pick.get(side), national(pick)) for side in ('home', 'away'))
    if not kickoff or not home or not away or home == away or not pick.get('market'):
        return None
    return f'{kickoff.astimezone(OSLO).date()}|{home}|{away}|{pick["market"]}'


def match_saved_picks(picks, rows):
    """Return results addressed to each original pick's ID, rejecting ambiguity."""
    out, seen = [], set()
    for pick in picks:
        mid = str(pick.get('matchId') or '')
        if not mid or mid in seen:
            continue
        kickoff = dt(pick.get('kickoff'))
        candidates = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            exact = str(row.get('id')) == mid
            if not exact:
                start = dt(row.get('utcDate'))
                if not kickoff or not start or abs(start - kickoff) > timedelta(hours=1):
                    continue
                if kickoff.astimezone(OSLO).date() != start.astimezone(OSLO).date():
                    continue
                is_national = national(pick)
                if any(result_team_key(pick.get(side), is_national) != result_team_key(
                        (row.get(side + 'Team') or {}).get('name'), is_national)
                       for side in ('home', 'away')):
                    continue
            candidates.append(row)
        # Even matching names cannot resolve two conflicting authoritative results.
        signatures = {(row.get('status'), repr(row.get('score'))) for row in candidates}
        if not candidates or len(signatures) != 1:
            continue
        row = deepcopy(candidates[0])
        row['sourceMatchId'] = str(row.get('sourceMatchId') or row.get('id'))
        if str(row.get('id')) != mid:
            row['id'] = mid
        seen.add(mid)
        out.append(row)
    return out


def normalize_uefa(row, source_url, competition='2014'):
    if not isinstance(row, dict) or not row.get('id'):
        return None
    kickoff = dt((row.get('kickOffTime') or {}).get('dateTime'))
    home, away = row.get('homeTeam') or {}, row.get('awayTeam') or {}
    # Explicitly exclude youth and different competitions/team classes.
    team_type = 'NATIONAL_MEN_TEAM_A' if competition == '2014' else 'DOMESTIC_MEN_TEAM_A'
    if (str((row.get('competition') or {}).get('id')) != competition
            or any(t.get('teamTypeDetail') != team_type for t in (home, away))
            or not kickoff):
        return None
    raw = row.get('score') or {}
    regular = raw.get('regular') or {}
    total = raw.get('total') or {}
    valid = lambda score: all(type(score.get(side)) is int and 0 <= score[side] <= 50
                              for side in ('home', 'away'))
    # A final total alone may include extra time. Never substitute it for 90 min.
    score = {'regularTime': regular if valid(regular) else {},
             'fullTime': total if valid(total) else {}, 'duration': 'EXTRA_TIME'}
    if valid(raw.get('halfTime') or {}):
        score['halfTime'] = raw['halfTime']
    return {
        'id': 'uefa:' + str(row['id']), 'utcDate': kickoff.isoformat(),
        'status': row.get('status'), 'score': score,
        'homeTeam': {'name': home.get('internationalName') or home.get('teamCode')},
        'awayTeam': {'name': away.get('internationalName') or away.get('teamCode')},
        'resultSource': 'UEFA', 'resultSourceUrl': source_url,
    }


def uefa_results(picks, fetch):
    rows = []
    for competition in sorted({uefa_competition(p) for p in picks if uefa_competition(p)}):
        days = sorted({dt(p['kickoff']).astimezone(OSLO).date() for p in picks
                       if uefa_competition(p) == competition and dt(p.get('kickoff'))})
        windows = []
        for day in days:
            season = day.year + (day.month >= 7)
            if not windows or (day - windows[-1][1][0]).days > 2 or windows[-1][0] != season:
                windows.append((season, [day]))
            else:
                windows[-1][1].append(day)
        # Short windows avoid silently accepting a truncated UEFA calendar.
        for year, selected in windows:
            url = CALENDAR_URL + '?' + urlencode({
                'competitionId': competition, 'seasonYear': year,
                'fromDate': min(selected).isoformat(), 'toDate': (max(selected) + timedelta(days=1)).isoformat(),
                'order': 'ASC', 'limit': MATCH_LIMIT, 'offset': 0,
            })
            payload = fetch(url)
            if not isinstance(payload, list) or len(payload) >= MATCH_LIMIT:
                raise ValueError('Invalid or incomplete UEFA results')
            rows.extend(item for raw in payload if (item := normalize_uefa(raw, url, competition)) is not None)
    return rows
