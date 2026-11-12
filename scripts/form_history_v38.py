"""Auditable match-form records for OddsGeneratoren.

Only source-marked completed fixtures with real nonnegative regular-time scores.
No API requests, fuzzy league links, LLMs, or guesses are performed here.
When two otherwise identical source records disagree about the score, neither
is silently promoted to verified history.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
import re
import unicodedata

HISTORY_DAYS = 180
OSLO = ZoneInfo('Europe/Oslo')


def utc(value):
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def source_of(row):
    ident = str(row.get('id') or '')
    if ident.startswith('apf:'):
        return 'API-Football'
    if ident.startswith('fdc:'):
        return 'football-data.co.uk'
    if ident.isdecimal():
        return 'football-data.org'
    return str(row.get('formSource') or 'ukjent kilde')


def _score(row):
    score = row.get('score') or {}
    duration = str(score.get('duration') or 'REGULAR').upper()
    # Providers often put extra-time or shootout results into fullTime.
    # Use only explicit 90-minute regulation-time values in those cases.
    if duration in ('EXTRA_TIME', 'PENALTY_SHOOTOUT'):
        result = score.get('regularTime') or {}
    else:
        result = score.get('fullTime') or {}
    h, a = result.get('home'), result.get('away')
    if type(h) is not int or type(a) is not int or not (0 <= h <= 30 and 0 <= a <= 30):
        return None
    return h, a


def regular_time_score(row):
    """Regulation-time goals only; reject unknown extra-time/penalty splits."""
    return _score(row)

def _source_rank(source):
    return {'football-data.org': 3, 'API-Football': 2,
            'Sportmonks': 2, 'football-data.co.uk': 1}.get(source, 0)


def verified_form_records(fixtures, team_id, before, *, limit=16, days=HISTORY_DAYS):
    """Return (newest-first records, reason codes), using ONLY exact team IDs.

    No name-based remapping is performed by this function. Provider-specific IDs
    (apf:/fdc:) remain distinct. One historical fixture is never counted twice.
    """
    cutoff = utc(before)
    if cutoff is None:
        raise ValueError('before must be timezone-aware')
    if team_id is None or isinstance(team_id, bool):
        return [], ['team_id_missing']
    tid = str(team_id)
    oldest = cutoff - timedelta(days=days)
    candidates, issues = [], []
    for row in fixtures:
        if not isinstance(row, dict):
            continue
        if row.get('status') != 'FINISHED':
            continue
        instant = utc(row.get('utcDate'))
        if instant is None:
            continue
        if not oldest <= instant < cutoff:
            continue
        home, away = (row.get('homeTeam') or {}), (row.get('awayTeam') or {})
        hid, aid = home.get('id'), away.get('id')
        if hid is None or aid is None or str(hid) == str(aid):
            continue
        if tid not in (str(hid), str(aid)):
            continue
        goals = _score(row)
        if goals is None:
            issues.append('invalid_score')
            continue
        home_goals, away_goals = goals
        side = 'home' if tid == str(hid) else 'away'
        scored, conceded = (home_goals, away_goals) if side == 'home' else (away_goals, home_goals)
        result = 'W' if scored > conceded else 'L' if scored < conceded else 'D'
        opponent = away if side == 'home' else home
        m_id = str(row.get('id') or '').strip()
        if not m_id:
            issues.append('missing_match_id')
            continue
        home_name = str(home.get('name') or home.get('shortName') or '').strip()
        away_name = str(away.get('name') or away.get('shortName') or '').strip()
        source = source_of(row)
        competition = row.get('competition') or {}
        rec = {
            'matchId': m_id, 'source': source, 'sourceMatchId': m_id,
            'competition': str(competition.get('name') or competition.get('code') or ''),
            'competitionCode': str(competition.get('code') or ''),
            'kickoffUtc': instant.isoformat().replace('+00:00','Z'),
            'localDate': instant.astimezone(OSLO).date().isoformat(),
            'homeTeam': {'id': hid, 'name': home_name},
            'awayTeam': {'id': aid, 'name': away_name},
            'homeGoals': home_goals, 'awayGoals': away_goals,
            'analyzedTeamId': team_id, 'analyzedTeamSide': side,
            'analyzedTeamGoals': scored, 'opponentGoals': conceded,
            'resultForAnalyzedTeam': result,
            'venueLabel': 'Hjemme' if side == 'home' else 'Borte',
            'opponent': str(opponent.get('name') or opponent.get('shortName') or '').strip(),
            'status': 'FINISHED', 'verified': True,
            # Names are retained only if actually provided by the original source.
            'displayComplete': bool(home_name and away_name),
        }
        if row.get('dateOnly') is True:
            rec['dateOnly'] = True
        if row.get('neutralVenue') is True:
            rec['neutralVenue'] = True
            rec['venueLabel'] = 'Nøytral bane'
        candidates.append(rec)

    # Same provider event ID in multiple downloads is a single event.
    by_id = defaultdict(list)
    for row in candidates:
        by_id[(row['source'], row['sourceMatchId'])].append(row)
    unique = []
    for records in by_id.values():
        signatures = {(r['homeTeam']['id'], r['awayTeam']['id'], r['homeGoals'],
                       r['awayGoals'], r['kickoffUtc']) for r in records}
        if len(signatures) != 1:
            issues.append('score_conflict')
            continue
        if len(records) > 1:
            issues.append('duplicate_merged')
        unique.append(records[0])

    # Also merge verified provider duplicates when *both* team IDs, league and
    # kickoff are alike. Do not merge by club names or calendar day alone.
    unique.sort(key=lambda r: (r['kickoffUtc'], r['matchId']), reverse=True)
    groups = []
    for row in unique:
        d = utc(row['kickoffUtc'])
        group = next((group for group in groups if
                      group[0]['homeTeam']['id'] == row['homeTeam']['id'] and
                      group[0]['awayTeam']['id'] == row['awayTeam']['id'] and
                      group[0]['competitionCode'] == row['competitionCode'] and
                      abs((utc(group[0]['kickoffUtc'])-d).total_seconds()) <= 3600), None)
        if group is None:
            groups.append([row])
        else:
            group.append(row)
    result = []
    for group in groups:
        if len({(r['homeGoals'], r['awayGoals']) for r in group}) > 1:
            issues.append('score_conflict')
            continue
        if len(group) > 1:
            issues.append('duplicate_merged')
        result.append(sorted(group,key=lambda r:(-_source_rank(r['source']),r['matchId']))[0])
    result.sort(key=lambda r:(r['kickoffUtc'],r['matchId']),reverse=True)
    return result[:limit], sorted(set(issues))


def model_rows(records):
    """Keep legacy model tuple shape; model and UI now use identical matches."""
    out=[]
    for r in records:
        out.append((utc(r['kickoffUtc']), r['analyzedTeamGoals'],
                    r['opponentGoals'], r['resultForAnalyzedTeam'],
                    r['awayTeam']['id'] if r['analyzedTeamSide']=='home' else r['homeTeam']['id']))
    return out


# Only explicit, reviewed cross-provider aliases. Do not try arbitrary
# substring matching: similar names can refer to different clubs.
_LINK_ALIASES = {
    'bolton wanderers': 'bolton', 'silkeborg if': 'silkeborg',
    'pec zwolle': 'zwolle', 'fc zwolle': 'zwolle',
    'hamburger sv': 'hsv', 'borussia monchengladbach': 'monchengladbach',
    'm gladbach': 'monchengladbach', 'borussia m gladbach': 'monchengladbach',
    'real sociedad de futbol': 'real sociedad',
    'olympique lyonnais': 'lyon', 'olympique lyon': 'lyon',
    'atletico de madrid': 'atletico madrid',
    'internazionale milano': 'internazionale', 'inter milan': 'internazionale',
    'besiktas jk': 'besiktas',
}


def _club_key(name):
    name = str(name or '').casefold().replace('ø','o').replace('æ','ae').replace('å','a')
    name = unicodedata.normalize('NFKD',name)
    name = ''.join(ch for ch in name if not unicodedata.combining(ch))
    name = re.sub(r'[^a-z0-9]+',' ',name).strip()
    # Generic FC/AFC removal is only an identity confirmation step.
    name = re.sub(r'^(fc|afc) | (fc|afc)$','',name).strip()
    return _LINK_ALIASES.get(name,name)



def source_identity_confirmed(expected_names, records):
    """Verify synthetic/odds links against recorded names, never by loose similarity."""
    expected={_club_key(x) for x in expected_names if _club_key(x)}
    observed=set()
    for row in records:
        club=row['homeTeam'] if row['analyzedTeamSide']=='home' else row['awayTeam']
        key=_club_key(club.get('name'))
        if key:observed.add(key)
    return bool(expected & observed)
