"""Source-attributed independent correct-score forecasts and a transparent aggregate.

The project does not silently scrape or invent Forebet, Vitibet, PredictZ,
WinDrawWin or other providers. An optional, dated CSV records explicitly
verified public predictions. When configured, the API-Football endpoint adds
only exact integer score forecasts for strictly matched fixture IDs.

Own Poisson-based score scenarios are shown SEPARATELY from independent sites.
No predicted score is presented as a calibrated correct-score betting edge.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from build_data import iso_datetime, name_score

KNOWN_SITES = {
    'forebet': ('Forebet', ('forebet.com',)),
    'vitibet': ('Vitibet', ('vitibet.com',)),
    'predictz': ('PredictZ', ('predictz.com',)),
    'windrawwin': ('WinDrawWin', ('windrawwin.com',)),
    'footballpredictions.net': ('FootballPredictions.net', ('footballpredictions.net',)),
    'api-football': ('API-Football Predictions', ('api-football.com',)),
    'api-football predictions': ('API-Football Predictions', ('api-football.com',)),
}


def exact_goals(value):
    """Do not mistake predictions like -1.5 or +2.5 for an exact score."""
    if type(value) is int and 0 <= value <= 8:
        return value
    if isinstance(value, str) and re.fullmatch(r'[0-8]', value.strip()):
        return int(value.strip())
    return None


def trusted_url(url, expected_hosts):
    try:
        parts = urlsplit(str(url).strip())
        host=(parts.hostname or '').lower()
        return (parts.scheme == 'https' and parts.username is None and parts.password is None
                and any(host == d or host.endswith('.'+d) for d in expected_hosts)
                and parts.port in (None, 443))
    except (ValueError, TypeError):
        return False


def safe_source(row):
    name = str(row.get('source') or '').strip().lower()
    if name not in KNOWN_SITES:return None
    label, hosts = KNOWN_SITES[name]
    url = str(row.get('source_url') or row.get('url') or '').strip()
    if not trusted_url(url, hosts):return None
    h = exact_goals(row.get('home_goals'))
    a = exact_goals(row.get('away_goals'))
    if h is None or a is None:return None
    return {'source':label, 'sourceUrl':url, 'homeGoals':h, 'awayGoals':a,
            'observedAt':str(row.get('observed_at') or '').strip(), 'entry':'manual'}


def valid_observation(observed, now, kickoff):
    try:
        at=iso_datetime(observed)
        if at.tzinfo is None:return False
        return now-timedelta(days=3) <= at <= now+timedelta(minutes=5) and at < kickoff
    except (TypeError, ValueError):
        return False


def load_csv_rows(path, fixtures, at):
    """Strict match by fixture ID OR date+both team names. Never cross-match."""
    if not path.is_file():return defaultdict(list),[]
    result=defaultdict(list);issues=[]
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f)
        if not {'date','home','away','source','source_url','home_goals','away_goals','observed_at'}.issubset(set(reader.fieldnames or [])):
            return result,['Prediksjons-CSV har feil kolonner']
        for row_number,row in enumerate(reader,start=2):
            entry=safe_source(row)
            if entry is None:
                issues.append(f'Ugyldig kilde eller resultat på CSV-rad {row_number}')
                continue
            try:
                matches=[]
                for match in fixtures:
                    start=iso_datetime(match['kickoff'])
                    if not row.get('date') or (start.date().isoformat() != row['date'].strip() and
                        start.astimezone(__import__('zoneinfo').ZoneInfo('Europe/Oslo')).date().isoformat() != row['date'].strip()):
                        continue
                    fixture_id=str(row.get('match_id') or '').strip()
                    if fixture_id and str(match.get('id')) != fixture_id:continue
                    if min(name_score(row['home'],match['home']),name_score(row['away'],match['away'])) < .84:continue
                    if not valid_observation(entry['observedAt'],at,start):continue
                    matches.append(str(match['id']))
                if len(matches)!=1:
                    issues.append(f'Uklart eller manglende kampoppslag på CSV-rad {row_number}')
                    continue
                result[matches[0]].append(entry)
            except (TypeError, ValueError, KeyError):
                issues.append(f'Ugyldig kampdata på CSV-rad {row_number}')
    return result,issues[:8]


def poisson_scenario(model):
    try:
        lam_h,lam_a=[float(x) for x in model['expectedGoals']]
        sample=model.get('sample') or []
        if len(sample)!=2 or min(sample)<3 or not (.1<=lam_h<=5 and .1<=lam_a<=5):return None
        possibilities=[(math.exp(-lam_h)*lam_h**h/math.factorial(h) *
                        math.exp(-lam_a)*lam_a**a/math.factorial(a),h,a)
                       for h in range(7) for a in range(7)]
        _,h,a=max(possibilities,key=lambda p:(p[0],-p[1]-p[2],-p[1]))
        return {'homeGoals':h,'awayGoals':a,'method':'Uavhengig Poisson-modell fra registrerte kampresultater'}
    except (ValueError,TypeError,KeyError,OverflowError):
        return None


def aggregate_sources(rows):
    """Equal weight per independent publisher; no invented consensus for 0/1."""
    by_source={}
    conflicted=set()
    for r in rows:
        source=r.get('source')
        if source in conflicted:continue
        if source not in by_source:
            by_source[source]=r
        else:
            # Ambiguous duplicate for one publisher: remove it instead of cherry-picking.
            if (r['homeGoals'],r['awayGoals']) != (by_source[source]['homeGoals'],by_source[source]['awayGoals']):
                by_source[source]=None
                conflicted.add(source)
    unique=sorted((r for r in by_source.values() if r is not None),key=lambda r:r['source'])
    if len(unique)<2:return unique,None
    h_mean=sum(x['homeGoals'] for x in unique)/len(unique)
    a_mean=sum(x['awayGoals'] for x in unique)/len(unique)
    h=int(math.floor(h_mean+.5)); a=int(math.floor(a_mean+.5))
    direction=lambda x: 'H' if x['homeGoals']>x['awayGoals'] else 'B' if x['homeGoals']<x['awayGoals'] else 'U'
    shares={letter:sum(1 for r in unique if direction(r)==letter) for letter in ('H','U','B')}
    return unique,{
        'homeGoals':h, 'awayGoals':a, 'sourceCount':len(unique),
        'meanHome':round(h_mean,2),'meanAway':round(a_mean,2),
        'method':'Aritmetisk snitt av én verifisert resultatprognose per kilde, avrundet til heltall',
        'mostCommonOutcome':max(shares,key=shares.get) if max(shares.values())>len(unique)/2 else None,
        'outcomeVotes':shares,
        'note':'Et samlet scenario, ikke en sannsynlighet for eksakt sluttresultat',
    }


def fetch_api_football(fixtures, at, key, max_fixtures=4):
    """Only when enabled; strict identity & start-time mapping; budgeted calls."""
    found=defaultdict(list);issues=[]
    if not key:return found,issues
    base='https://v3.football.api-sports.io'
    headers={'x-apisports-key':key,'User-Agent':'OddsGeneratoren3000/1.4'}
    local_date=at.astimezone(__import__('zoneinfo').ZoneInfo('Europe/Oslo')).date().isoformat()
    def request(path):
        with urlopen(Request(base+path,headers=headers),timeout=20) as resp:
            return json.load(resp).get('response') or []
    try:
        events=request('/fixtures?'+urlencode({'date':local_date,'timezone':'Europe/Oslo'}))
    except Exception as exc:
        return found,['API-Football kampoversikt: '+type(exc).__name__]
    used=set()
    for m in fixtures[:max_fixtures]:
        try:
            kickoff=iso_datetime(m['kickoff']);candidates=[]
            if kickoff<=at:continue
            for raw in events:
                fixture=raw.get('fixture') or {}
                if abs((iso_datetime(fixture['date'])-kickoff).total_seconds())>3600:continue
                h=(raw.get('teams') or {}).get('home') or {}
                a=(raw.get('teams') or {}).get('away') or {}
                hs=name_score(m['home'],h.get('name') or '')
                aws=name_score(m['away'],a.get('name') or '')
                if min(hs,aws)<.84:continue
                candidates.append(int(fixture['id']))
            if len(candidates)!=1 or candidates[0] in used:continue
            used.add(candidates[0]); fixture_id=candidates[0]
            details=request('/predictions?'+urlencode({'fixture':fixture_id}))
            if not details:continue
            goals=((details[0].get('predictions') or {}).get('goals') or {})
            h=exact_goals(goals.get('home'));a=exact_goals(goals.get('away'))
            if h is None or a is None:continue
            found[str(m['id'])].append({
                'source':'API-Football Predictions','sourceUrl':'https://www.api-football.com/',
                'homeGoals':h,'awayGoals':a,'observedAt':at.isoformat(),'entry':'api',
            })
        except (KeyError,TypeError,ValueError,TimeoutError) as exc:
            issues.append('API-Football resultatanslag: '+type(exc).__name__)
        except Exception as exc:
            issues.append('API-Football tjeneste: '+type(exc).__name__)
    return found,issues[:5]


def build(snapshot, at, csv_file, api_key='', max_fixtures=8):
    matches={str(m['id']):m for m in snapshot.get('matches',[]) if m.get('id')}
    selected=[];visited=set()
    for p in [*(snapshot.get('recommendations') or []),*(snapshot.get('safeBets') or []),*(snapshot.get('highRisk') or [])]:
        mid=str(p.get('matchId') or '')
        if mid in matches and mid not in visited:
            visited.add(mid); selected.append(matches[mid])
    if len(selected)<max_fixtures:
        other=sorted((m for mid,m in matches.items() if mid not in visited),key=lambda m:m.get('kickoff') or '')
        for m in other:
            try:
                if iso_datetime(m['kickoff'])>at and m.get('status') in ('SCHEDULED','TIMED'):
                    selected.append(m)
            except (KeyError,TypeError,ValueError):pass
            if len(selected)>=max_fixtures:break
    selected=selected[:max_fixtures]
    csv_rows,issues=load_csv_rows(csv_file,selected,at)
    api_rows,api_issues=fetch_api_football(selected,at,api_key,max_fixtures=min(4,max_fixtures))
    issues.extend(api_issues)
    games=[]
    for m in selected:
        rows=list(csv_rows.get(str(m['id']),[]))+list(api_rows.get(str(m['id']),[]))
        # Respect independent score fields stored in core snapshot predictions.
        for external in m.get('predictions') or []:
            entry=safe_source({'source':str(external.get('source') or '').strip().lower(),
                               'source_url':external.get('url'),
                               'home_goals':(external.get('score') or {}).get('home'),
                               'away_goals':(external.get('score') or {}).get('away'),
                               'observed_at':external.get('observedAt') or at.isoformat()})
            if entry and valid_observation(entry['observedAt'],at,iso_datetime(m['kickoff'])):rows.append(entry)
        forecasts,combined=aggregate_sources(rows)
        games.append({'matchId':str(m['id']),'home':m['home'],'away':m['away'],
                      'kickoff':m['kickoff'],'league':m.get('league'),
                      'sources':forecasts,'consensus':combined,
                      'ownModel':poisson_scenario(m.get('model') or {})})
    snapshot['scorePredictions']={
        'games':games, 'sourceForecasts':sum(len(m['sources']) for m in games),
        'fixturesWithConsensus':sum(bool(m['consensus']) for m in games),
        'issues':issues[:10],
        'method':'Lik vekt for ulike, kildeangitte resultattips; krever minst to uavhengige kilder for samlet prognose',
        'coverageNote':'Forebet, Vitibet, PredictZ og WinDrawWin kan inkluderes ved manuelt registrerte, datostemplede resultattips med kildelenker. Kildeinnholdet kontrolleres ikke automatisk. API-Football krever egen API-nøkkel. Egen modell holdes separat.'
    }
    return snapshot


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('snapshot',type=Path)
    args=p.parse_args()
    if not args.snapshot.is_file():raise SystemExit('Kandidatfil mangler')
    original=json.loads(args.snapshot.read_text(encoding='utf-8'))
    at=iso_datetime(original.get('generatedAt') or datetime.now(timezone.utc).isoformat())
    try:
        changed=build(original,at,ROOT/'data'/'score_predictions.csv',
                      os.getenv('API_FOOTBALL_KEY','').strip())
        tmp=args.snapshot.with_name(args.snapshot.name+'.scores.tmp')
        tmp.write_text(json.dumps(changed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        tmp.replace(args.snapshot)
        print('SCORE_CONSENSUS external='+str(changed['scorePredictions']['sourceForecasts'])+
              ' combined='+str(changed['scorePredictions']['fixturesWithConsensus']))
    except Exception as exc:
        # Extra previews must never take the daily picks offline.
        print('WARNING score consensus not loaded: '+type(exc).__name__,file=sys.stderr)


if __name__=='__main__':main()
