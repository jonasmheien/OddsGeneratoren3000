#!/usr/bin/env python3
"""Generate a dated, source-labelled static football dashboard snapshot.

No API keys go into published site/data/ files. The model is a transparent
Poisson baseline and has NOT been backtested or calibrated for betting use.
"""
from __future__ import annotations
import csv
import json
import math
import os
import re
import statistics
import time
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from recommend import curated_picks, category_picks
from form_v21 import adjusted_form, effective_form_sample, opponent_indices
from expanded_sources_v23 import discover as discover_extra, odds_remaining
from odds_first_v25 import preview_sports, fixtures_from_quotes
from market_expansion import extend_goal_probabilities, first_half_probabilities, corner_probabilities

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ['ODDS_OUTPUT_PATH']) if os.environ.get('ODDS_OUTPUT_PATH') else ROOT / 'site' / 'data' / 'today.json'
OSLO = ZoneInfo('Europe/Oslo')
BASE = 'https://api.football-data.org/v4'
ODDS_BASE = 'https://api.the-odds-api.com/v4'
# Match competition codes from football-data.org to The Odds API sports keys.
SPORT_BY_COMPETITION = {
    'PL':'soccer_epl', 'CL':'soccer_uefa_champs_league',
    'SA':'soccer_italy_serie_a', 'BL1':'soccer_germany_bundesliga',
    'PD':'soccer_spain_la_liga', 'FL1':'soccer_france_ligue_one',
    'DED':'soccer_netherlands_eredivisie', 'PPL':'soccer_portugal_primeira_liga',
    'ELC':'soccer_efl_champ', 'EL':'soccer_uefa_europa_league',
    'APF-NO1':'soccer_norway_eliteserien', 'APF-SE1':'soccer_sweden_allsvenskan',
    'APF-SE2':'soccer_sweden_superettan', 'APF-DK1':'soccer_denmark_superliga',
    'APF-ES2':'soccer_spain_segunda_division', 'APF-FI1':'soccer_finland_veikkausliiga',
}
# Free plan: 500 credits/month as of project setup. One region × two markets
# costs about 2 credits per league per run (provider rules may change).
# One daily run × 5 leagues × 2 markets × 31 days = ~310 credits/month at most under the current credit formula.
ODDS_SPORTS_PER_RUN = min(5, max(1, int(os.getenv('ODDS_SPORTS_PER_RUN', '5'))))
# Extra bookmaker markets cost per event. Keep to two events by default to
# respect free-tier monthly credits; adjust only after checking account usage.
ODDS_EXTRA_EVENTS = min(5, max(0, int(os.getenv('ODDS_EXTRA_EVENTS', '3'))))
EXTRA_MARKET_KEYS = 'btts,team_totals,totals_h1,alternate_totals'
# Corners requires historical corners stats; enable when a licensed stats feed is available.
if os.getenv('ODDS_CORNERS_ENABLED','') == '1':
    EXTRA_MARKET_KEYS += ',alternate_totals_corners'
MARKETS = ('H', 'U', 'B', 'O25', 'U25', 'O35', 'BTTS')


def sports_today(fixtures: list, now: datetime, max_sports: int = ODDS_SPORTS_PER_RUN, target_date=None) -> list[str]:
    """Use API quota on eligible upcoming competitions, not arbitrary fixed leagues."""
    counts = defaultdict(int)
    today = target_date or now.astimezone(OSLO).date()
    for fixture in fixtures:
        if fixture.get('status') not in ('SCHEDULED', 'TIMED'):
            continue
        try:
            kickoff = iso_datetime(fixture['utcDate'])
        except (KeyError, TypeError, ValueError):
            continue
        if kickoff <= now or kickoff.astimezone(OSLO).date() != today:
            continue
        code = (fixture.get('competition') or {}).get('code')
        if code in SPORT_BY_COMPETITION:
            counts[SPORT_BY_COMPETITION[code]] += 1
    return [key for key, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:max_sports]]


def fetch_json(url: str, headers: dict | None = None):
    req = Request(url, headers={'User-Agent': 'OddsGeneratoren/0.3 (personal research)', **(headers or {})})
    with urlopen(req, timeout=28) as response:
        return json.load(response)


def iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def normalized(value: str) -> str:
    s = (value or '').replace('ø', 'o').replace('Ø','O').replace('æ','ae').replace('Æ','Ae').replace('å','a').replace('Å','A')
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace('&', ' and ')
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    words = [x for x in s.split() if x not in {'fc', 'afc', 'cf', 'ac', 'sc', 'as', 'the', 'club', 'football', 'calcio', '1907', '1908'}]
    return ' '.join(words)


# A compact list of common provider-name variants. These improve matching,
# without treating unrelated clubs as the same side.
TEAM_NAME_ALIASES = {
    'barca': 'barcelona',
    'fc barca': 'barcelona',
    'atleti': 'atletico madrid',
    'atletico de madrid': 'atletico madrid',
    'club atletico de madrid': 'atletico madrid',
    'man united': 'manchester united',
    'man utd': 'manchester united',
    'man city': 'manchester city',
    'manchester utd': 'manchester united',
    'shaktar': 'shakhtar donetsk',
    'shakhtar': 'shakhtar donetsk',
    'shakhtar donetsk': 'shakhtar donetsk',
    'sl bratislava': 'slovan bratislava',
    'slovan': 'slovan bratislava',
    'slovan bratislava': 'slovan bratislava',
    'inter milan': 'internazionale',
    'inter': 'internazionale',
    'internazionale milano': 'internazionale',
    'lask': 'lask linz',
    'lask linz': 'lask linz',
    'psg': 'paris saint germain',
    'paris sg': 'paris saint germain',
    'paris saint germain': 'paris saint germain',
    'bodo glimt': 'bodo glimt',
    'bodo glimt fk': 'bodo glimt',
}


def club_identity(value: str) -> str:
    n = normalized(value)
    return TEAM_NAME_ALIASES.get(n, n)


def identity_score(a: str, b: str) -> float:
    # Exact canonical aliases are very strong, but all nonalias matches still
    # pass the ordinary conservative similarity threshold.
    a_id, b_id = club_identity(a), club_identity(b)
    if a_id and a_id == b_id:
        return 1.0
    return name_score(a, b)


def team_candidate_names(match: dict, side: str) -> list[str]:
    return [x for x in [match.get(side)] + list(match.get(side + 'Aliases') or []) if x]


def event_identity_score(match: dict, event: dict, side: str) -> float:
    return max((identity_score(name, event.get(side + '_team', ''))
                for name in team_candidate_names(match, side)), default=0.0)


def name_score(a: str, b: str) -> float:
    a, b = normalized(a), normalized(b)
    if a == b and a:
        return 1.0
    a_words, b_words = set(a.split()), set(b.split())
    if a_words and b_words and a_words == b_words:
        return .99
    overlap = len(a_words & b_words) / max(len(a_words), len(b_words), 1)
    return .55 * SequenceMatcher(None, a, b).ratio() + .45 * overlap


def fixed_odds_event(match: dict, odds_events: list) -> dict:
    """Match names + kickoff, using official full names and safe aliases.

    Do not attach odds if the team identity is uncertain or there are multiple
    plausible matches. This is more important than filling every fixture.
    """
    candidates = []
    date = iso_datetime(match['kickoff'])
    for event in odds_events:
        try:
            seconds = abs((iso_datetime(event['commence_time']) - date).total_seconds())
            if seconds > 2 * 3600:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        hs = event_identity_score(match, event, 'home')
        aw = event_identity_score(match, event, 'away')
        if min(hs, aw) < .77:
            continue
        score = (hs + aw) / 2 - .02 * seconds / 3600
        candidates.append((score, event))
    candidates.sort(key=lambda x: x[0], reverse=True)
    if not candidates:
        return {}
    # Different event IDs at similarly high scores indicate ambiguity, e.g.
    # names like 'United'. Refuse to silently cross-match those odds.
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < .025:
        return {}
    return candidates[0][1]


def recent_team_form(matches: list, before: datetime, team_id: int, limit: int = 16) -> list:
    values = []
    for m in matches:
        if m.get('status') != 'FINISHED':
            continue
        try:
            kickoff = iso_datetime(m['utcDate'])
        except (KeyError, ValueError):
            continue
        if kickoff >= before:
            continue
        home = (m.get('homeTeam') or {}).get('id')
        away = (m.get('awayTeam') or {}).get('id')
        if team_id not in (home, away):
            continue
        score = (m.get('score') or {}).get('fullTime') or {}
        hg, ag = score.get('home'), score.get('away')
        if not isinstance(hg, int) or not isinstance(ag, int):
            continue
        ish = home == team_id
        gf, ga = (hg, ag) if ish else (ag, hg)
        values.append((kickoff, gf, ga, 'W' if gf > ga else 'D' if gf == ga else 'L', away if ish else home))
    values.sort(reverse=True)
    return values[:limit]


def poisson_pmf(lam: float, k: int) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def model_probabilities(home_form: list, away_form: list) -> dict | None:
    if min(len(home_form), len(away_form)) < 3:
        return None
    # Conservative shrinkage towards baseline; not a calibrated predictive model.
    n_h, n_a = len(home_form), len(away_form)
    def rate(form, idx, prior):
        n = len(form)
        return (sum(x[idx] for x in form) + 6 * prior) / (n + 6)
    home_attack = rate(home_form, 1, 1.45)
    away_def = rate(away_form, 2, 1.45)
    away_attack = rate(away_form, 1, 1.15)
    home_def = rate(home_form, 2, 1.15)
    lh = max(.35, min(3.4, (home_attack * away_def) ** .5 * 1.06))
    la = max(.30, min(3.2, (away_attack * home_def) ** .5 * .95))
    hp = [poisson_pmf(lh, x) for x in range(13)]
    ap = [poisson_pmf(la, x) for x in range(13)]
    norm = sum(hp) * sum(ap)
    prob = {k: 0.0 for k in MARKETS}
    for h in range(13):
        for a in range(13):
            p = hp[h] * ap[a] / norm
            prob['H' if h > a else 'U' if h == a else 'B'] += p
            prob['O25' if h + a >= 3 else 'U25'] += p
            if h + a >= 4:
                prob['O35'] += p
            if h > 0 and a > 0:
                prob['BTTS'] += p
    model={'probabilities': {k: round(v, 4) for k,v in prob.items()},
           'expectedGoals': [round(lh,2), round(la,2)],
           'sample': [n_h, n_a], 'quality': 'exploratory' if min(n_h,n_a) < 5 else 'basic'}
    extend_goal_probabilities(model)
    return model


def extract_market_odds(event: dict, match: dict, asof: datetime | None = None) -> dict:
    """Parse bookmaker markets, always keying by BOTH line and team.

    Duplicate book+market observations from featured + event endpoints do
    not inflate the bookmaker count. Invalid/unknown points are excluded.
    """
    values = defaultdict(dict)
    for book in event.get('bookmakers', []):
        bookname = book.get('key') or book.get('title') or 'Ukjent'
        for market in book.get('markets', []):
            updated = market.get('last_update') or book.get('last_update')
            if asof is not None:
                if not updated:continue
                try:
                    age=(asof-iso_datetime(updated)).total_seconds()/3600
                    if not -1<=age<=12:continue
                except (TypeError,ValueError):continue
            key=market.get('key')
            for item in market.get('outcomes', []):
                try:price=float(item.get('price'))
                except (ValueError,TypeError):continue
                if not 1.01<=price<=1000:continue
                name=str(item.get('name','')).strip()
                low=name.lower()
                point=item.get('point')
                selection=None
                if key=='h2h':
                    if name_score(name,event.get('home_team',''))>=.77:selection='H'
                    elif name_score(name,event.get('away_team',''))>=.77:selection='B'
                    elif low=='draw':selection='U'
                elif key in ('totals','alternate_totals'):
                    if point in (1.5,2.5,3.5) and low in ('over','under'):
                        selection= ('O' if low=='over' else 'U')+f'{int(point*10):02d}'
                elif key=='btts' and low=='yes':
                    selection='BTTS'
                elif key in ('team_totals','alternate_team_totals'):
                    # The Odds API records the target team in 'description';
                    # an unlabeled line must never be assigned to a side.
                    desc=str(item.get('description') or '')
                    if low=='over' and point in (.5,1.5):
                        if name_score(desc,event.get('home_team',''))>=.77:
                            selection='THO'+f'{int(point*10):02d}'
                        elif name_score(desc,event.get('away_team',''))>=.77:
                            selection='TAO'+f'{int(point*10):02d}'
                elif key in ('totals_h1','alternate_totals_h1'):
                    if point in (.5,1.5) and low in ('over','under'):
                        selection='H1'+('O' if low=='over' else 'U')+f'{int(point*10):02d}'
                elif key=='alternate_totals_corners' and point in (8.5,9.5) and low=='over':
                    selection='CO'+f'{int(point*10):02d}'
                if selection:
                    values[selection][bookname]={'price':price,'book':bookname,'updated':updated}
    ret={}
    for code,bookvalues in values.items():
        choices=list(bookvalues.values())
        prices=[v['price'] for v in choices]
        median=statistics.median(prices)
        timestamps=[v['updated'] for v in choices if v.get('updated')]
        ret[code]={'price':round(median,2),'source':'The Odds API · bookmaker-median',
                   'books':len(choices),'lastUpdated':max(timestamps) if timestamps else None,
                   'sampleBook':min(choices,key=lambda v:abs(v['price']-median))['book']}
    return ret


def fetch_extra_event_markets(sports: list[str], odds_events: list[dict], now: datetime,
                              max_events: int = ODDS_EXTRA_EVENTS) -> tuple[list[dict], list[str]]:
    """Limited per-fixture odds enrichment without spending the monthly quota blindly.

    Enrichment is optional: missing markets never block the core analysis.
    No request is made without an explicit active ODDS_API_KEY.
    """
    key=os.getenv('ODDS_API_KEY','').strip()
    if not key or max_events<=0:return odds_events,[]
    updated=list(odds_events)
    issues=[]
    selected=[]
    today=now.astimezone(OSLO).date()
    for event in odds_events:
        if event.get('sport_key') not in sports:continue
        try:
            kickoff=iso_datetime(event['commence_time'])
            if kickoff <= now+timedelta(minutes=40) or kickoff.astimezone(OSLO).date()!=today:continue
        except (KeyError,ValueError,TypeError):continue
        if event.get('id'):
            selected.append(event)
    selected.sort(key=lambda e:e.get('commence_time',''))
    # Approximate budget ceiling of 15 provider credits per daily run.
    # Featured odds cost ~2 per sport; extra event odds ~4 per event.
    allowed_events=max(0,min(max_events,(15-2*len(sports))//len(EXTRA_MARKET_KEYS.split(','))))
    for event in selected[:allowed_events]:
        sport=event.get('sport_key')
        eid=event.get('id')
        args=urlencode({'apiKey':key,'regions':'eu','markets':EXTRA_MARKET_KEYS,'oddsFormat':'decimal'})
        url=f'{ODDS_BASE}/sports/{sport}/events/{eid}/odds?{args}'
        try:
            req=Request(url,headers={'User-Agent':'OddsGeneratoren/1.2'})
            with urlopen(req,timeout=28) as response:
                remaining=response.headers.get('x-requests-remaining')
                extra=json.load(response)
            if isinstance(extra,dict) and isinstance(extra.get('bookmakers'),list):
                # Keep featured and extra market entries. The parser deduplicates
                # by bookmaker ID and exact selection market.
                event['bookmakers']=list(event.get('bookmakers',[]))+extra['bookmakers']
                event['extraMarketsLoaded']=True
            if remaining is not None and int(remaining)<35:
                issues.append('Odds API: lav gjenværende kvote, flere ekstramarkeder ble ikke hentet')
                break
        except Exception as exc:
            issues.append('Ekstramarkeder (ikke-kritisk): '+type(exc).__name__)
            # If the provider rejects this market set, avoid repeated futile calls.
            if type(exc).__name__ == 'HTTPError':break
    return updated,issues

def read_manual_models(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def predictions_for(m: dict, rows: list[dict]) -> list[dict]:
    result = []
    d = iso_datetime(m['kickoff']).astimezone(OSLO).date().isoformat()
    for row in rows:
        if row.get('date', '').strip() != d:
            continue
        if min(name_score(m['home'],row.get('home','')),name_score(m['away'],row.get('away',''))) < .82:
            continue
        probabilities = {}
        for k in MARKETS:
            raw = (row.get(k) or '').strip().replace(',', '.')
            if raw:
                try:
                    number = float(raw)
                    if 0 <= number <= 100:
                        probabilities[k] = number/100
                except ValueError:
                    pass
        name = (row.get('source') or '').strip()
        if name and probabilities:
            result.append({'source': name, 'url': (row.get('url') or '').strip(), 'probabilities': probabilities, 'entry': 'manual'})
    return result


def missing_form_teams(fixtures: list, now: datetime, limit: int = 16, target_date=None) -> list[int]:
    """Find CL sides lacking even five past results in our fixture history.

    Team endpoints can return domestic-league results as well as CL matches.
    Only select teams involved in today's upcoming CL games.
    """
    pending=[]
    for m in fixtures:
        if (m.get('competition') or {}).get('code') != 'CL' or m.get('status') not in ('SCHEDULED','TIMED'):
            continue
        try:
            start=iso_datetime(m['utcDate'])
        except (KeyError,ValueError,TypeError):
            continue
        if start<=now or start.astimezone(OSLO).date()!=(target_date or now.astimezone(OSLO).date()):
            continue
        for item in ('homeTeam','awayTeam'):
            team_id=(m.get(item) or {}).get('id')
            if team_id and len(recent_team_form(fixtures,start,team_id))<5 and team_id not in pending:
                pending.append(team_id)
        if len(pending)>=limit:
            return pending[:limit]
    return pending


def independent_api_predictions(fixtures: list, now: datetime, api_key: str,
                                max_predictions: int = 10, target_date=None) -> tuple[dict, list[str]]:
    """Optionally fetch a limited second model from the documented API-Football
    Predictions API. Match team names AND start times, reject ambiguous matches.
    Free-tier access depends on the provider's current season permissions.
    Never turn unverified model opinions into bookmaker prices.
    """
    issues=[]
    if not api_key:
        return {}, issues
    local_date=(target_date or now.astimezone(OSLO).date()).isoformat()
    api_base='https://v3.football.api-sports.io'
    headers={'x-apisports-key': api_key}
    try:
        events=fetch_json(api_base+'/fixtures?'+urlencode({'date':local_date,'timezone':'Europe/Oslo'}),headers).get('response',[])
        if not isinstance(events,list):
            raise ValueError('Unexpected fixtures format')
    except Exception as exc:
        return {}, ['API-Football fixtures: '+type(exc).__name__]
    mapped={}
    used=set()
    for raw in fixtures:
        if raw.get('status') not in ('SCHEDULED','TIMED'):
            continue
        try:
            start=iso_datetime(raw['utcDate'])
            if start<=now or start.astimezone(OSLO).date().isoformat()!=local_date:
                continue
        except (KeyError,TypeError,ValueError):
            continue
        home=(raw.get('homeTeam') or {}).get('name') or (raw.get('homeTeam') or {}).get('shortName') or ''
        away=(raw.get('awayTeam') or {}).get('name') or (raw.get('awayTeam') or {}).get('shortName') or ''
        matches=[]
        for event in events:
            f=event.get('fixture') or {}
            try:
                if abs((iso_datetime(f['date'])-start).total_seconds())>3600:
                    continue
                h=(event.get('teams') or {}).get('home',{}).get('name','')
                a=(event.get('teams') or {}).get('away',{}).get('name','')
                hs,aws=name_score(home,h),name_score(away,a)
                if min(hs,aws)<.78:
                    continue
                matches.append((hs+aws,int(f['id'])))
            except (ValueError,TypeError,KeyError):
                continue
        matches.sort(reverse=True)
        if len(matches)!=1 or matches[0][1] in used:
            continue
        used.add(matches[0][1]);mapped[str(raw.get('id'))]=matches[0][1]
        if len(mapped)>=max_predictions:
            break
    predictions={}
    for match_id,external_id in mapped.items():
        try:
            rows=fetch_json(api_base+'/predictions?'+urlencode({'fixture':external_id}),headers).get('response',[])
            if not isinstance(rows,list) or not rows:
                continue
            pct=((rows[0].get('predictions') or {}).get('percent') or {})
            if not all(k in pct for k in ('home','draw','away')):
                continue
            numbers={code:float(str(pct[field]).strip().rstrip('%'))/100.0 for code,field in (('H','home'),('U','draw'),('B','away'))}
            if not all(0<=x<=1 for x in numbers.values()) or not .95<=sum(numbers.values())<=1.05:
                continue
            predictions[match_id]=[{'source':'API-Football Predictions',
                'url':'https://www.api-football.com/',
                'probabilities':numbers,'entry':'api'}]
        except Exception as exc:
            issues.append('API-Football Predictions: '+type(exc).__name__)
    return predictions,issues


def build_snapshot(now: datetime, fixtures: list, odds_events: list | None, manual_models: list, errors: list, status: dict, external_predictions: dict | None = None, target_date=None) -> dict:
    today = target_date or now.astimezone(OSLO).date()
    cutoff = today + timedelta(days=1)
    output = []
    strengths = opponent_indices(fixtures, now)
    for raw in fixtures:
        if raw.get('status') in ('CANCELLED','POSTPONED'):
            continue
        try:
            k = iso_datetime(raw['utcDate'])
        except (KeyError, ValueError):
            continue
        local_day = k.astimezone(OSLO).date()
        if not today <= local_day <= cutoff:
            continue
        home = raw.get('homeTeam') or {}
        away = raw.get('awayTeam') or {}
        if not home.get('id') or not away.get('id'):
            continue
        if k <= now and raw.get('status') == 'FINISHED':
            continue
        hf = recent_team_form(fixtures, k, home['id'])
        af = recent_team_form(fixtures, k, away['id'])
        m = {'id': str(raw.get('id') or ''), 'league': (raw.get('competition') or {}).get('name') or 'Annen',
             'leagueCode': (raw.get('competition') or {}).get('code') or '',
             'leagueCrest': (raw.get('competition') or {}).get('emblem'),
             'homeCrest': home.get('crest'), 'awayCrest': away.get('crest'),
             'home': home.get('shortName') or home.get('name') or 'Hjemmelag',
             'away': away.get('shortName') or away.get('name') or 'Bortelag',
             'homeAliases': [home.get('name')],
             'awayAliases': [away.get('name')],
             'kickoff': k.isoformat(), 'status': raw.get('status') or 'SCHEDULED',
             'formHome': ''.join(x[3] for x in hf), 'formAway': ''.join(x[3] for x in af),
             'model': model_probabilities(adjusted_form(hf, strengths, k), adjusted_form(af, strengths, k)), 'odds': {}, 'predictions': []}
        if m['model'] is not None:
            m['model']['effectiveSample'] = [effective_form_sample(hf, k), effective_form_sample(af, k)]
            m['model']['modelMethod'] = 'strength_adjusted_v21'
            m['model']['historyWindowDays'] = 180
        if m['model'] is not None:
            m['model']['probabilities'].update(first_half_probabilities(fixtures,k,home['id'],away['id']))
            m['model']['probabilities'].update(corner_probabilities(fixtures,k,home['id'],away['id']))
        if odds_events is not None:
            od = fixed_odds_event(m, odds_events)
            m['odds'] = extract_market_odds(od, m, now)
        m['predictions'] = predictions_for(m, manual_models) + (external_predictions or {}).get(str(m['id']), [])
        output.append(m)
    output.sort(key=lambda m: m['kickoff'])
    todays = [m for m in output if iso_datetime(m['kickoff']).astimezone(OSLO).date() == today]
    picks = curated_picks(todays, now, limit=5)
    # Each category has its own shortlist. A higher-scoring risky option for
    # a match must not hide an independently valid favorite for that match.
    safe_bets = category_picks(todays, now, 'safe', limit=5)
    high_risk = category_picks(todays, now, 'high', limit=5)
    # Opposing outcomes in the very same game must not be recommended as
    # independently sound bets across Safe Bets and High Risk.
    def incompatible(a,b):
        opposite=[{'H','B','U'},{'O15','U15'},{'O25','U25'},
                  {'O35','U35'},{'H1O15','H1U15'}]
        return any(a in group and b in group and a != b for group in opposite)
    high_risk=[p for p in high_risk if not any(str(p['matchId'])==str(s['matchId']) and incompatible(p['market'],s['market']) for s in safe_bets)]
    # Main recommendations must obey the same cross-category rule.
    picks=[p for p in picks if not any(str(p['matchId'])==str(s['matchId']) and incompatible(p['market'],s['market']) for s in safe_bets)]
    # Join stable presentation metadata from the exact same fixture ID.
    # Crests are only displayed after the site owner has obtained the rights;
    # football-data.org expressly notes ownership by the clubs.
    match_by_id={str(m['id']):m for m in todays}
    for choice in (picks, safe_bets, high_risk):
        for p in choice:
            match=match_by_id.get(str(p.get('matchId')),{})
            for field in ('homeCrest','awayCrest','leagueCrest'):
                p[field]=match.get(field)
            confirmed=[]
            code=p.get('market')
            for pred in match.get('predictions') or []:
                v=(pred.get('probabilities') or {}).get(code)
                if isinstance(v,(float,int)) and abs(v-p['probability'])<=.12 and v*float(p['price'])>=1:
                    name=pred.get('source')
                    if name and name not in confirmed:
                        confirmed.append(name)
            p['predictionSources']=confirmed
    # Explain coverage and upstream provenance to the interface. Unconnected
    # prediction websites must NEVER be represented as integrated sources.
    active_today = [m for m in todays if m.get('status') in ('SCHEDULED','TIMED') and iso_datetime(m['kickoff']) > now]
    coverage = {
        'upcomingMatches': len(active_today),
        'matchedOdds': sum(bool(m.get('odds')) for m in active_today),
        'withModel': sum(bool(m.get('model')) for m in active_today),
        'externalPredictions': sum(len(m.get('predictions') or []) for m in active_today),
        'manualPredictions': sum(1 for m in active_today for pred in (m.get('predictions') or []) if pred.get('entry')=='manual'),
        'apiPredictions': sum(1 for m in active_today for pred in (m.get('predictions') or []) if pred.get('entry')=='api'),
        'safeFound': len(safe_bets), 'highFound': len(high_risk),
        'targetPerCategory': [3, 5],
    }
    sources = [
        {'name':'football-data.org', 'role':'Kampdata og form', 'state':'connected' if status.get('fixtures')=='ok' else 'unavailable'},
        {'name':'The Odds API', 'role':'Bookmakerodds', 'state':'connected' if status.get('odds')=='ok' else 'unavailable'},
        {'name':'API-Football Predictions', 'role':'Uavhengig modell',
         'state':'connected' if status.get('externalPredictionsStatus')=='ok' else 'unavailable' if status.get('externalPredictionsStatus')=='error' else 'not_connected'},
        {'name':'Eksterne prognoser', 'role':'Kildeangitte, manuelt innlagte vurderinger',
         'state':'manual' if coverage['manualPredictions'] else 'not_connected'},
    ]
    return {'version': 3, 'recommendations':picks, 'safeBets':safe_bets, 'highRisk':high_risk,
            'coverage':coverage,'sources':sources,
            'visualAssets':{'licensedCrests':os.getenv('SHOW_LICENSED_CRESTS','').strip()=='1'},
            'qualityGate':{
                'minimumFormMatchesPerTeam':5, 'minimumFormHighRisk':3, 'minimumFormStandard':4, 'minimumBookmakers':2, 'maximumOddsAgeHours':12,
                'explanation':'Intern, ikke-kalibrert Poisson-modell + form + bookmakerpriser. Ingen garantert verdi.'}, 'generatedAt': now.isoformat(), 'localDate': today.isoformat(),
            'dataStatus': status, 'errors': errors,
            'method': 'Konservativ ikke-kalibrert Poisson-baseline fra siste inntil 6 registrerte resultater. Screening er en hypotese, ikke dokumentert positiv forventningsverdi.',
            'matches': output}


def main():
    now = datetime.now(timezone.utc)
    preview_offset = int(os.getenv('ODDS_TARGET_DAY_OFFSET', '0'))
    if preview_offset not in (0, 1):
        raise ValueError('ODDS_TARGET_DAY_OFFSET must be 0 or 1')
    date = now.astimezone(OSLO).date() + timedelta(days=preview_offset)
    key = os.getenv('FOOTBALL_DATA_API_KEY', '').strip()
    odds_key = os.getenv('ODDS_API_KEY', '').strip()
    errors = []
    status = {'fixtures': 'not_configured', 'odds': 'not_configured'}
    fixtures = []
    odds_events = None
    last_football_request = 0.0
    def fetch_football(url):
        nonlocal last_football_request
        # Free tier permits only ~10 API calls/minute. Stay below that.
        wait=max(0.0, 6.5-(time.monotonic()-last_football_request)) if last_football_request else 0
        if wait:
            time.sleep(wait)
        last_football_request=time.monotonic()
        return fetch_json(url, {'X-Auth-Token': key})
    sports = []
    if key:
        # One small discovery query finds today's eligible fixtures. Pull full
        # form for just the selected competitions to avoid global truncation.
        query = {'dateFrom': (date - timedelta(days=1)).isoformat(),
                 'dateTo': (date + timedelta(days=2)).isoformat()}
        url = BASE + '/matches?' + urlencode(query)
        try:
            response = fetch_football(url)
            day_fixtures = response.get('matches', [])
            if not isinstance(day_fixtures, list):
                raise ValueError('Unknown API fixture response')
            sports = sports_today(day_fixtures, now, target_date=date)
            fixtures_by_id = {m['id']: m for m in day_fixtures if m.get('id')}
            sport_to_code = {v: k for k,v in SPORT_BY_COMPETITION.items()}
            for sport in sports:
                code = sport_to_code[sport]
                if code.startswith('APF-'):
                    continue  # API-Football leagues have their own history source.
                history_url = BASE + f'/competitions/{code}/matches?' + urlencode({
                    'dateFrom': (date - timedelta(days=180)).isoformat(),
                    'dateTo': (date + timedelta(days=2)).isoformat(), 'limit': 500})
                try:
                    hist = fetch_football(history_url).get('matches', [])
                    if not isinstance(hist, list):
                        raise ValueError('Unknown API history response')
                    fixtures_by_id.update({m['id']: m for m in hist if m.get('id')})
                except Exception as exc:
                    errors.append(f'Historikk ({code}): feil ({type(exc).__name__})')
            # CL form is often sparse in November. Supplement it with the
            # teams' league results, while staying inside the API rate limit.
            needs=missing_form_teams(list(fixtures_by_id.values()),now,target_date=date)
            team_requests_ok=0
            for team_id in needs:
                url=BASE+f'/teams/{team_id}/matches?'+urlencode({
                    'dateFrom':(date-timedelta(days=180)).isoformat(),
                    'dateTo':date.isoformat(), 'status':'FINISHED','limit':100})
                try:
                    rows=fetch_football(url).get('matches', [])
                    if isinstance(rows,list):
                        fixtures_by_id.update({m['id']:m for m in rows if m.get('id')})
                        team_requests_ok+=1
                except Exception as exc:
                    # Not all leagues / team endpoints are available on free plans.
                    errors.append(f'Team form ({team_id}): {type(exc).__name__}')
            fixtures = list(fixtures_by_id.values())
            status['teamFormRequests']=team_requests_ok
            status['fixtures'] = 'ok'
            status['fixtureCount'] = len(fixtures)
        except Exception as exc:
            errors.append('Kampdata: feil ved henting (' + type(exc).__name__ + ')')
            status['fixtures'] = 'error'
    # Add explicitly matched API-Football league fixtures only when the
    # account grants actual current-season coverage. No synthetic scores.
    if os.getenv('API_FOOTBALL_KEY','').strip():
        extra, extra_notes = discover_extra(date,now,os.environ['API_FOOTBALL_KEY'],max_history_calls=12)
        errors.extend(extra_notes)
        if extra:
            combined={str(m['id']):m for m in fixtures if m.get('id')}
            combined.update({str(m['id']):m for m in extra if m.get('id')})
            fixtures=list(combined.values())
            sports=sports_today(fixtures,now,target_date=date)
        status['apiFootballExtraFixtures']=sum(m.get('status')=='SCHEDULED' for m in extra)
        status['apiFootballExtraHistory']=sum(m.get('status')=='FINISHED' for m in extra)
    if odds_key:
        odds_events = []
        explicit = os.getenv('ODDS_SPORTS', '').strip()
        sports = ([x.strip() for x in explicit.split(',') if x.strip()] if explicit
                  else sports)
        if preview_offset == 1 and not explicit:
            # football-data.org may omit UEFA's Thursday fixtures on the free tier.
            # Query only two known, active football competitions in next-day mode.
            sports = preview_sports(sports, max_sports=ODDS_SPORTS_PER_RUN)
        # The sports endpoint has zero quota cost and reports remaining
        # credits in response headers. Leave room for later daily editions.
        remaining=None
        try:
            remaining=odds_remaining(odds_key)
        except (OSError,ValueError,TimeoutError) as exc:
            errors.append('Odds quota check: '+type(exc).__name__)
        status['oddsCreditsRemaining']=remaining
        if remaining is not None:
            # Each h2h + totals request costs two credits (one region).
            # Reserve 48 credits and up to 6 credits for potential extras.
            # Previews need only four credits for the two standard markets.
            # Keep at least 20 credits for the regular morning analysis.
            reserve=20 if preview_offset == 1 else 54
            affordable=max(0,(remaining-reserve)//2)
            sports=sports[:affordable]
        status['requestedLeagues'] = sports[:ODDS_SPORTS_PER_RUN]
        status['oddsMarketKeys'] = ['h2h', 'totals']
        for sport in sports[:ODDS_SPORTS_PER_RUN]:
            try:
                params = urlencode({'apiKey': odds_key, 'regions': 'eu', 'markets': 'h2h,totals', 'oddsFormat':'decimal'})
                items = fetch_json(f'{ODDS_BASE}/sports/{sport}/odds/?{params}')
                if not isinstance(items, list):
                    raise ValueError('Unknown API odds response')
                odds_events.extend(items)
            except Exception as exc:
                errors.append(f'Odds ({sport}): hentefeil ({type(exc).__name__})')
        if odds_events and (remaining is None or remaining >= 64):
            odds_events,extra_issues=fetch_extra_event_markets(sports,odds_events,now)
            errors.extend(extra_issues)
        elif odds_events:
            status['extraMarketsSkippedQuota']=True
        status['extraEventsLoaded']=sum(bool(e.get('extraMarketsLoaded')) for e in odds_events)
        status['odds'] = 'ok' if odds_events else 'empty' if not sports else 'error'
        status['oddsEventCount'] = len(odds_events)
        if preview_offset == 1 and odds_events:
            # True bookmaker-listed fixtures, even when another feed omits them.
            # Synthetic provider-scoped IDs carry NO fake historical form.
            recovered=fixtures_from_quotes(odds_events,now,date,fixtures)
            if recovered:
                fixtures.extend(recovered)
                status['oddsFixtureSource'] = 'The Odds API (bookmaker listings)'
            status['oddsFirstFixtures'] = len(recovered)
    external={}
    third_key=os.getenv('API_FOOTBALL_KEY','').strip()
    if third_key and fixtures:
        external,external_errors=independent_api_predictions(fixtures, now, third_key, max_predictions=10, target_date=date)
        errors.extend(external_errors)
        status['externalPredictionsStatus']='ok' if external else 'error' if external_errors else 'empty'
        status['externalPredictionsCount']=len(external)
    else:
        status['externalPredictionsStatus']='not_configured'
    snapshot = build_snapshot(now, fixtures, odds_events,
                              read_manual_models(ROOT / 'data' / 'manual_predictions.csv'),
                              errors, status, external_predictions=external, target_date=date)
    # Visibility into the reason a full match programme produces few picks.
    current_matches = [m for m in snapshot['matches']
                       if iso_datetime(m['kickoff']).astimezone(OSLO).date() == date
                       and m.get('status') in ('SCHEDULED', 'TIMED')
                       and iso_datetime(m['kickoff']) > now]
    coverage_by_league = {}
    for m in current_matches:
        code = m.get('leagueCode') or 'OTHER'
        c = coverage_by_league.setdefault(code, {
            'upcoming': 0, 'withOdds': 0, 'withModel': 0, 'eligible': 0})
        c['upcoming'] += 1
        if m.get('odds'):
            c['withOdds'] += 1
        if m.get('model'):
            c['withModel'] += 1
    for pick in snapshot['recommendations']:
        code = next((m.get('leagueCode') for m in current_matches
                     if str(m.get('id')) == str(pick.get('matchId'))), None)
        if code in coverage_by_league:
            coverage_by_league[code]['eligible'] += 1
    snapshot['dataStatus']['coverageByLeague'] = coverage_by_league
    snapshot['dataStatus']['analysisReadiness'] = {
        'upcoming':snapshot['coverage']['upcomingMatches'],
        'matchedOdds':snapshot['coverage']['matchedOdds'],
        'withModel':snapshot['coverage']['withModel'],
        'recommended':len(snapshot['recommendations']),
        'safe':len(snapshot['safeBets']),
        'highRisk':len(snapshot['highRisk']),
        'message': ('ingen kamp med tilgjengelig bookmakerodds' if snapshot['coverage']['upcomingMatches'] and not snapshot['coverage']['matchedOdds'] else
                    'ingen spill passerte kvalitetsfiltrene' if snapshot['coverage']['matchedOdds'] and not (snapshot['safeBets'] or snapshot['highRisk'] or snapshot['recommendations']) else
                    'analysert')
    }
    for code, c in sorted(coverage_by_league.items()):
        print(f"COVERAGE {code}: {c['upcoming']} upcoming, {c['withOdds']} with odds, "
              f"{c['withModel']} with model, {c['eligible']} picks")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Built {len(snapshot['matches'])} fixtures. Fixture status={status['fixtures']}, odds status={status['odds']}; candidates={len(snapshot['recommendations'])}; requested leagues={status.get('requestedLeagues', [])}")
    if errors:
        for error in errors:
            print('WARN:', error, file=sys.stderr)
    # Fail the deployment rather than overwrite a previously valid snapshot with an empty API error.
    if status['fixtures'] != 'ok':
        print('ERROR: kampdata mangler, behold forrige utgave', file=sys.stderr)
        sys.exit(1)
    if not odds_key or status['odds'] == 'error':
        print('ERROR: odds-kilden er ikke tilgjengelig, behold forrige utgave', file=sys.stderr)
        sys.exit(1)
    if snapshot['coverage']['upcomingMatches'] and not snapshot['coverage']['matchedOdds']:
        print('ERROR: kommende kamper uten noen matchede odds, prøv igjen i neste morgenkjøring', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
