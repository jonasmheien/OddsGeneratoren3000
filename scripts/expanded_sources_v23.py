"""Optional API-Football fixture bridge for leagues missing at football-data.org.

Explicitly conservative: never derive a betting probability without enough real,
completed games for both sides. Team IDs are namespaced to avoid merging providers.
No bookmaker prices are fabricated. Respect API-Football's request allocation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

BASE = 'https://v3.football.api-sports.io'

# Exact league/country pairs; never treat a cup, reserves or lower tier as the
# senior league. Odds keys from The Odds API /sports endpoint documentation.
EXTRA_LEAGUES = {
    ('Norway','Eliteserien'): ('APF-NO1','soccer_norway_eliteserien'),
    ('Sweden','Allsvenskan'): ('APF-SE1','soccer_sweden_allsvenskan'),
    ('Sweden','Superettan'): ('APF-SE2','soccer_sweden_superettan'),
    ('Denmark','Superliga'): ('APF-DK1','soccer_denmark_superliga'),
    ('Denmark','Superligaen'): ('APF-DK1','soccer_denmark_superliga'),
    ('Spain','Segunda División'): ('APF-ES2','soccer_spain_segunda_division'),
    ('Spain','Segunda Division'): ('APF-ES2','soccer_spain_segunda_division'),
    ('Spain','LaLiga2'): ('APF-ES2','soccer_spain_segunda_division'),
    ('Spain','LaLiga 2'): ('APF-ES2','soccer_spain_segunda_division'),
    ('Finland','Veikkausliiga'): ('APF-FI1','soccer_finland_veikkausliiga'),
}

# Past matches are essential; without them the existing qualifier rejects tips.
# One dated discovery call plus at most 12 calls for recent team results.
MAX_TEAM_HISTORY_CALLS = 12


def _id(value):
    return f'apf:{value}' if type(value) is int and value > 0 else None


def _score_value(value):
    return value if type(value) is int and value >= 0 else None


def normalize_fixture(item: dict, *, allow_unlisted: bool = False) -> dict | None:
    """Return football-data.org-like fields using provider-scoped identifiers.

    For past team history, keep other real leagues as context, but never admit
    their upcoming games as supported odds competitions.
    """
    try:
        fixture, league = item['fixture'], item['league']
        teams = item['teams']
        home, away = teams['home'], teams['away']
        date = str(fixture['date'])
        instant = datetime.fromisoformat(date.replace('Z','+00:00'))
        if instant.tzinfo is None:
            return None
        fixture_id = _id(fixture['id'])
        home_id, away_id = _id(home['id']), _id(away['id'])
        if not fixture_id or not home_id or not away_id or home_id == away_id:
            return None
        label = (str((league.get('country') or '').strip()), str((league.get('name') or '').strip()))
        chosen = EXTRA_LEAGUES.get(label)
        if not chosen and not allow_unlisted:
            return None
        status_code = (fixture.get('status') or {}).get('short')
        if status_code in ('FT','AET','PEN'):
            status = 'FINISHED'
        elif status_code in ('NS','TBD'):
            status = 'SCHEDULED'
        elif status_code in ('PST',):
            status = 'POSTPONED'
        elif status_code in ('CANC', 'ABD', 'AWD', 'WO'):
            status = 'CANCELLED'
        elif status_code in ('1H','2H','HT','ET','BT','P','INT','LIVE'):
            status = 'IN_PLAY'
        else:
            return None
        goals = item.get('goals') or {}
        result = {'home':_score_value(goals.get('home')),'away':_score_value(goals.get('away'))}
        if status not in ('FINISHED','IN_PLAY'):
            result = {'home':None,'away':None}
        duration = ('EXTRA_TIME' if status_code=='AET' else
                    'PENALTY_SHOOTOUT' if status_code=='PEN' else 'REGULAR')
        regular = result
        if status_code in ('AET','PEN'):
            final_90 = (item.get('score') or {}).get('fulltime') or {}
            regular = {'home':_score_value(final_90.get('home')),
                       'away':_score_value(final_90.get('away'))}
        return {'id':fixture_id, 'utcDate':instant.astimezone(timezone.utc).isoformat(),
                'status':status,'homeTeam':{'id':home_id,'name':home.get('name'),'shortName':home.get('name'), 'crest':None},
                'awayTeam':{'id':away_id,'name':away.get('name'),'shortName':away.get('name'), 'crest':None},
                'competition':{'code':chosen[0] if chosen else 'APF-OTHER',
                               'name':league.get('name'),'emblem':None},
                'score':{'fullTime':result,'regularTime':regular,'duration':duration}}
    except (KeyError,ValueError,TypeError,AttributeError):
        return None


def request_api(path: str, params: dict, key: str):
    req = Request(f'{BASE}/{path}?{urlencode(params)}',headers={
        'x-apisports-key':key,'User-Agent':'OddsGeneratoren/2.3 (research)'})
    with urlopen(req,timeout=28) as response:
        obj = json.load(response)
    if not isinstance(obj,dict) or not isinstance(obj.get('response'),list):
        raise ValueError('API-Football: invalid response')
    if obj.get('errors'):
        raise ValueError('API-Football: provider error')
    return obj['response']


def discover(date, now, key, *, max_history_calls=MAX_TEAM_HISTORY_CALLS, request=request_api):
    """Fetch only real, relevant upcoming fixtures and bounded team history.

    If provider denies current-season data, return no extra fixtures and let
    existing football-data.org operate exactly as before.
    """
    notes=[]
    if not key:
        return [], notes
    try:
        rows = request('fixtures',{'date':date.isoformat()},key)
    except (OSError,ValueError,TimeoutError) as exc:
        return [], [f'API-Football fixture discovery unavailable: {type(exc).__name__}']
    chosen = []
    for row in rows:
        item = normalize_fixture(row)
        if item and item['status'] == 'SCHEDULED' and datetime.fromisoformat(item['utcDate']) > now:
            chosen.append((item,row))
    chosen.sort(key=lambda pair:(pair[0]['utcDate'],pair[0]['id']))
    fixtures = [x for x,_ in chosen]
    ids = []
    for _,raw in chosen:
        for key_side in ('home','away'):
            team_id = (raw.get('teams') or {}).get(key_side,{}).get('id')
            if type(team_id) is int and team_id not in ids:
                ids.append(team_id)
    # Budget guard applies to unique teams, not games; deterministic truncation.
    calls = min(max(0,int(max_history_calls)),MAX_TEAM_HISTORY_CALLS)
    for team in ids[:calls]:
        try:
            rows = request('fixtures',{'team':team,'last':16},key)
            for row in rows:
                item = normalize_fixture(row,allow_unlisted=True)
                if item and item['status']=='FINISHED' and datetime.fromisoformat(item['utcDate']) < now:
                    fixtures.append(item)
        except (OSError,ValueError,TimeoutError) as exc:
            notes.append(f'API-Football team history {team} unavailable: {type(exc).__name__}')
    dedup = {m['id']:m for m in fixtures}
    return list(dedup.values()), notes


def available_sports(fixtures, now):
    """Only sports with independently observed, scheduled games today."""
    keys={code:key for code,key in EXTRA_LEAGUES.values()}
    counts={}
    for m in fixtures:
        if m.get('status')!='SCHEDULED':
            continue
        if (m.get('competition') or {}).get('code') not in keys:
            continue
        try:
            instant=datetime.fromisoformat(m['utcDate'])
        except (KeyError, ValueError,TypeError):
            continue
        if instant <= now or instant.astimezone(ZoneInfo('Europe/Oslo')).date()!=now.astimezone(ZoneInfo('Europe/Oslo')).date():
            continue
        sport=keys[m['competition']['code']]
        counts[sport]=counts.get(sport,0)+1
    return [x for x,n in sorted(counts.items(), key=lambda x:(-x[1],x[0]))]


def results_for(ids, key, *, request=request_api):
    """Retrieve real API-Football scores for saved provider-prefixed fixture IDs."""
    valid=[]
    for identifier in ids:
        value=str(identifier)
        if value.startswith('apf:') and value[4:].isdigit():
            valid.append(value[4:])
    if not key or not valid:
        return []
    out=[]
    for start in range(0,len(valid),20):
        rows=request('fixtures',{'ids':'-'.join(valid[start:start+20])},key)
        for row in rows:
            normalized=normalize_fixture(row,allow_unlisted=True)
            if normalized and normalized['id'] in {f'apf:{x}' for x in valid}:
                out.append(normalized)
    return out


def odds_remaining(key, *, urlopen_fn=urlopen):
    """Read free /sports endpoint quota headers, never expose the API key."""
    if not key:
        return None
    req=Request('https://api.the-odds-api.com/v4/sports/?'+urlencode({'apiKey':key}),
                headers={'User-Agent':'OddsGeneratoren/2.3 (research)'})
    with urlopen_fn(req, timeout=28) as response:
        remaining=response.headers.get('x-requests-remaining')
        return int(remaining) if remaining and str(remaining).isdigit() else None
