"""OddsGeneratoren v1.4: optional non-core markets, never fabricates prices or form.

Runs AFTER build_data.py and BEFORE lifecycle.py daily promotion. Extends the
candidate JSON; all IO failures keep the main daily edition functional.

Market coverage is source-constrained: The Odds API extra event markets +
football-data.org observed historical results when supplied. A quote without
independent evidence is ONLY a watch item, never a recommended bet.
"""
from __future__ import annotations

import json
import math
import os
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from build_data import SPORT_BY_COMPETITION, fixed_odds_event, iso_datetime, name_score, normalized

ODDS_URL = 'https://api.the-odds-api.com/v4'
FD_URL = 'https://api.football-data.org/v4'
PLAYER_LEAGUES = {'PL', 'BL1', 'SA', 'PD', 'FL1'}
LEAGUE_CODES = {'soccer_epl': 'PL', 'soccer_germany_bundesliga': 'BL1',
                'soccer_italy_serie_a': 'SA', 'soccer_spain_la_liga': 'PD',
                'soccer_france_ligue_one': 'FL1'}
CATEGORY_NAMES = {
    'corners': 'Hjørnespark', 'cards': 'Kort', 'goalscorer': 'Målscorer',
    'goals': 'Mål', 'team_goals': 'Lagmål', 'first_half': '1. omgang',
    'btts': 'Begge lag scorer',
}


def get_json(url: str, headers=None):
    request = Request(url, headers={'User-Agent': 'OddsGeneratoren-v1.4', **(headers or {})})
    with urlopen(request, timeout=22) as response:
        remaining = response.headers.get('x-requests-remaining')
        return json.load(response), (int(remaining) if remaining is not None else None)


def iso_now(value):
    return iso_datetime(value) if isinstance(value, str) else value


def quote_is_fresh(quote, now, minimum=2):
    try:
        age=(now-iso_datetime(quote['lastUpdated'])).total_seconds()/3600
        return (1.08 <= float(quote['price']) <= 16 and int(quote['books']) >= minimum
                and -1 <= age <= 12)
    except (TypeError, ValueError, KeyError):
        return False


def normal_key(name):
    return normalized(str(name or '')).replace(' ', '-')


def quote_market(market_key, item, event):
    """Return a UNIQUE code for an explicit line, team or player. No guessing."""
    name=str(item.get('name') or '').strip().lower()
    line=item.get('point')
    def is_half_point(v):
        return isinstance(v,(float,int)) and abs(v%1-.5)<1e-8 and 0.5<=v<=20.5
    if market_key in ('alternate_totals_corners','alternate_totals_cards'):
        if not is_half_point(line) or name not in ('over','under'):return None
        group='CO' if market_key.endswith('corners') else 'CA'
        return group+('O' if name=='over' else 'U')+str(int(round(line*10)))
    if market_key in ('team_totals','alternate_team_totals'):
        if not isinstance(line,(float,int)) or line not in (0.5,1.5,2.5):return None
        if name not in ('over','under'):return None
        desc=str(item.get('description') or '').strip()
        h=name_score(desc,event.get('home_team') or '')
        a=name_score(desc,event.get('away_team') or '')
        if min(max(h,a),1)<.84 or abs(h-a)<.10:return None
        side='H' if h>a else 'A'
        return 'T'+side+('O' if name=='over' else 'U')+f'{int(line*10):02d}'
    if market_key=='btts':
        return 'BTTS' if name=='yes' else 'BTTSN' if name=='no' else None
    if market_key in ('totals_h1','alternate_totals_h1'):
        if line not in (0.5,1.5) or name not in ('over','under'):return None
        return 'H1'+('O' if name=='over' else 'U')+f'{int(line*10):02d}'
    if market_key=='player_goal_scorer_anytime':
        # The Odds API uses an outcome with name='Yes' and description=player.
        if name not in ('yes','over'):return None
        player=str(item.get('description') or '').strip()
        if not (3<=len(player)<=70) or not re.search('[a-zA-ZÀ-ž]', player):return None
        return 'GS:'+normal_key(player)
    return None


def bookmaker_quotes(event, market_types, at):
    """Deduplicate across bookmaker IDs; keep outcome identity exact."""
    observations=defaultdict(dict)
    players={}
    for bookmaker in event.get('bookmakers', []):
        book_id=str(bookmaker.get('key') or bookmaker.get('title') or '').strip()
        if not book_id:continue
        for market in bookmaker.get('markets', []):
            key=market.get('key')
            if key not in market_types:continue
            updated=market.get('last_update') or bookmaker.get('last_update')
            try:age=(at-iso_datetime(updated)).total_seconds()/3600
            except (ValueError,TypeError):continue
            if not -1<=age<=12:continue
            for item in market.get('outcomes', []):
                code=quote_market(key,item,event)
                if not code:continue
                try:price=float(item['price'])
                except (TypeError,ValueError,KeyError):continue
                if not 1.08<=price<=16:continue
                observations[code][book_id]={'price':price,'at':updated}
                if code.startswith('GS:'):
                    players[code]=str(item.get('description')).strip()
    out={}
    for code, by_book in observations.items():
        rows=list(by_book.values())
        out[code]={
            'price':round(statistics.median(x['price'] for x in rows),2),
            'books':len(rows), 'lastUpdated':max(x['at'] for x in rows),
            'source':'The Odds API', 'player':players.get(code),
        }
    return out


def statistics_rows(history, team_id):
    """Total corners and yellow cards from actual FINISHED records only."""
    data=[]
    for item in history:
        if item.get('status')!='FINISHED':continue
        h=item.get('homeTeam') or {};a=item.get('awayTeam') or {}
        if team_id not in (h.get('id'),a.get('id')):continue
        hs=h.get('statistics') or {};as_=a.get('statistics') or {}
        if not isinstance(hs,dict) or not isinstance(as_,dict):continue
        try:timestamp=iso_datetime(item['utcDate'])
        except (TypeError,ValueError,KeyError):continue
        outcome={}
        for metric,fields in [('corners',('corner_kicks',)),('cards',('yellow_cards',))]:
            vals=[hs.get(fields[0]),as_.get(fields[0])]
            if all(type(x) is int and 0<=x<=25 for x in vals):outcome[metric]=sum(vals)
        if outcome:data.append((timestamp,outcome))
    return [row for _,row in sorted(data,reverse=True)[:15]]


def observed_probability(home_history,away_history,kind,line,side):
    samples=[ [s[kind] for s in history if kind in s][:10] for history in (home_history,away_history)]
    if min(len(s) for s in samples)<8:return None,0
    totals=samples[0]+samples[1]
    hits=sum((v>line if side=='over' else v<line) for v in totals)
    # Mild shrinkage. Exploratory frequency, NOT calibrated predictive probability.
    return round((hits+2)/(len(totals)+4),4),min(len(s) for s in samples)


def scorer_probability(scorers, player_name, home, away):
    hits=[]
    for entry in scorers:
        person=(entry.get('player') or {}).get('name') or ''
        team=(entry.get('team') or {}).get('name') or ''
        if normal_key(person)!=normal_key(player_name):continue
        if max(name_score(team,home),name_score(team,away))<.77:continue
        goals=entry.get('goals'); appearances=entry.get('playedMatches')
        if type(goals) is not int or type(appearances) is not int or goals<3 or appearances<8:continue
        # Goals per appearance, shrunk towards a modest baseline; excludes penalty
        # and lineup effects we cannot verify in a morning batch.
        rate=(goals+2*.18)/(appearances+2)
        p=1-math.exp(-min(rate,1.7))
        hits.append((round(p,4),appearances,goals))
    return hits[0] if len(hits)==1 else None


def evaluate(quote, probability, kind, sample, now):
    """Independent checks prevent treating bookmaker odds as proven model edge."""
    if probability is None or sample<8 or not quote_is_fresh(quote,now,minimum=2):return False
    price=float(quote['price']); implied=1/price
    # Uncalibrated rates must be near market consensus and only modest edges.
    return (.33<=probability<=.80 and 1.30<=price<=3.6
            and abs(probability-implied)<=.12
            and .03<=probability*price-1<=.30)


def enrich_existing_coverage(snapshot):
    """Expose real quotes already fetched by v1.2 for goal/half/team/Btts markets."""
    counts=defaultdict(int)
    for match in snapshot.get('matches') or []:
        for code,q in (match.get('odds') or {}).items():
            if not isinstance(q,dict) or not q.get('price'):continue
            if code.startswith(('TH','TA')):kind='team_goals'
            elif code.startswith('H1'):kind='first_half'
            elif code.startswith('CO'):kind='corners'
            elif code.startswith('CA'):kind='cards'
            elif code.startswith('GS:'):kind='goalscorer'
            elif code.startswith(('O','U')):kind='goals'
            elif code.startswith('BTTS'):kind='btts'
            else:continue
            counts[kind]+=1
    return counts



# Existing v1.2 fulltime, team and half-time markets should remain visible
# to the market scanner, without double-counting a selected main tip.
EXISTING_MARKETS = {
    'O15':('goals','Over 1,5 mål'), 'U15':('goals','Under 1,5 mål'),
    'O25':('goals','Over 2,5 mål'), 'U25':('goals','Under 2,5 mål'),
    'O35':('goals','Over 3,5 mål'), 'U35':('goals','Under 3,5 mål'),
    'BTTS':('btts','Begge lag scorer'),
    'THO05':('team_goals','Hjemmelaget over 0,5 mål'),
    'THO15':('team_goals','Hjemmelaget over 1,5 mål'),
    'TAO05':('team_goals','Bortelaget over 0,5 mål'),
    'TAO15':('team_goals','Bortelaget over 1,5 mål'),
    'H1O05':('first_half','1. omgang over 0,5 mål'),
    'H1O15':('first_half','1. omgang over 1,5 mål'),
    'H1U15':('first_half','1. omgang under 1,5 mål'),
}


def existing_market_watch(snapshot, now):
    """Show only real, fresh quotes not already recommended in the main lists."""
    picked={(str(p.get('matchId')),p.get('market'))
            for name in ('recommendations','safeBets','highRisk')
            for p in (snapshot.get(name) or [])}
    result=[]
    for m in snapshot.get('matches') or []:
        if m.get('status') not in ('SCHEDULED','TIMED'):continue
        try:
            kickoff=iso_datetime(m['kickoff'])
            if kickoff<=now+timedelta(minutes=40):continue
        except (KeyError,ValueError,TypeError):continue
        for code,(kind,description) in EXISTING_MARKETS.items():
            q=(m.get('odds') or {}).get(code) or {}
            if not quote_is_fresh(q,now):continue
            if (str(m.get('id')),code) in picked:continue
            model_probability=(m.get('model') or {}).get('probabilities',{}).get(code)
            probability=(round(float(model_probability),4)
                         if isinstance(model_probability,(int,float)) and .02<=model_probability<=.98 else None)
            reasons=['Verifisert bookmakerpris, men ikke kvalifisert som et hovedtips',
                     f'Pris fra {q["books"]} bookmakere']
            if probability is not None:
                reasons.append(f'Eget, ikke-kalibrert modellanslag: {probability*100:.0f} %')
            result.append({'matchId':m.get('id'),'home':m.get('home'),'away':m.get('away'),
                'league':m.get('league'),'kickoff':m.get('kickoff'),
                'market':code,'label':description,'marketType':kind,'price':q['price'],
                'bookmakers':q['books'],'oddsUpdatedAt':q['lastUpdated'],
                'probability':probability,'verified':False,'rationale':reasons,
                'source':'The Odds API','sampleSize':min((m.get('model') or {}).get('sample') or [0])})
    return result


def watch_special_goal_markets(match, event, at):
    """Inspect extra goal lines absent from v1.2, never claim a calibrated edge."""
    categories={'team_totals','alternate_team_totals','btts','totals_h1','alternate_totals_h1'}
    quotes=bookmaker_quotes(event,categories,at)
    out=[]
    exp=(match.get('model') or {}).get('expectedGoals') or []
    base=(match.get('model') or {}).get('probabilities') or {}
    for code,q in quotes.items():
        if not quote_is_fresh(q,at):continue
        p=None;kind=None;description=None
        if code.startswith('T') and len(code)>=5 and code[1] in ('H','A'):
            kind='team_goals';line=int(code[3:])/10
            side=code[2];which=code[1]
            description=f'{"Hjemmelaget" if which=="H" else "Bortelaget"} {"over" if side=="O" else "under"} {line:g} mål'
            if len(exp)==2:
                try:
                    lam=float(exp[0 if which=='H' else 1])
                    prob=1-sum(math.exp(-lam)*lam**x/math.factorial(x) for x in range(int(line)+1))
                    p=prob if side=='O' else 1-prob
                except (ValueError,OverflowError,TypeError):pass
        elif code=='BTTSN':
            kind='btts';description='Begge lag scorer: Nei'
            if isinstance(base.get('BTTS'),(float,int)):p=1-float(base['BTTS'])
        elif code=='BTTS':
            kind='btts';description='Begge lag scorer: Ja'
            if isinstance(base.get('BTTS'),(float,int)):p=float(base['BTTS'])
        elif code.startswith('H1'):
            kind='first_half';line=int(code[3:])/10
            description=f'1. omgang {"over" if code[2]=="O" else "under"} {line:g} mål'
            over=base.get('H1O'+f'{int(line*10):02d}')
            if isinstance(over,(float,int)):p=float(over) if code[2]=='O' else 1-float(over)
        if not kind or not description:continue
        out.append({'matchId':match.get('id'),'home':match.get('home'),'away':match.get('away'),
            'league':match.get('league'),'kickoff':match.get('kickoff'),
            'market':code,'label':description,'marketType':kind,
            'price':q['price'],'bookmakers':q['books'],'oddsUpdatedAt':q['lastUpdated'],
            'probability':round(p,4) if p is not None else None,'verified':False,
            'rationale':[f'Verifisert bookmakerpris fra {q["books"]} bookmakere',
                         'Kun markedsovervåkning, ikke nok uavhengig grunnlag til å anbefale'],
            'source':'The Odds API'})
    return out

def load_history_for_fixture(match,token,cache,issues):
    """One fixture details + two team histories, only if the feed provides stats."""
    if not token:return [],[]
    game_id=str(match.get('id') or '')
    if not game_id.isdigit():return [],[]
    headers={'X-Auth-Token':token}
    try:
        game,_=get_json(f'{FD_URL}/matches/{game_id}',headers)
        h_id=(game.get('homeTeam') or {}).get('id');a_id=(game.get('awayTeam') or {}).get('id')
        if not h_id or not a_id:return [],[]
        results=[]
        for team_id in (h_id,a_id):
            if team_id not in cache:
                query=urlencode({'status':'FINISHED','limit':15})
                response,_=get_json(f'{FD_URL}/teams/{team_id}/matches?{query}',headers)
                cache[team_id]=statistics_rows(response.get('matches') or [], team_id)
            results.append(cache[team_id])
        return results[0],results[1]
    except (HTTPError,URLError,ValueError,KeyError,TimeoutError) as exc:
        issues.append('Historiske kort/hjørnespark: '+type(exc).__name__)
        return [],[]


def label(code,person=None):
    if code.startswith(('CO','CA')):
        family='hjørnespark' if code.startswith('CO') else 'kort'
        side='Over' if code[2]=='O' else 'Under'
        return f'{side} {int(code[3:])/10:g} {family}'
    if code.startswith('GS:'):return f'{person} scorer' if person else 'Målscorer'
    return code


def run(snapshot,key,stats_key,at,cap=1):
    """Returns augmented JSON; unsupported/missing data never crashes core pipeline."""
    issues=[]; watch=[]; tips=[]; counted=enrich_existing_coverage(snapshot)
    remaining=None; budgets={'events':0,'odds_requests':0}
    scheduled=[]
    for m in snapshot.get('matches') or []:
        try:kick=iso_datetime(m['kickoff'])
        except (ValueError,TypeError,KeyError):continue
        if (m.get('status') in ('SCHEDULED','TIMED') and kick>at+timedelta(minutes=50)
            and kick.astimezone().date()>=at.astimezone().date()
            and m.get('leagueCode') in SPORT_BY_COMPETITION):scheduled.append(m)
    # Match the fixture ID only after a two-sided name + kickoff cross-check.
    by_sport=defaultdict(list)
    for m in scheduled:by_sport[SPORT_BY_COMPETITION[m['leagueCode']]].append(m)
    matched=[]
    if key:
        for sport, games in sorted(by_sport.items(),key=lambda x:-len(x[1]))[:4]:
            try:
                endpoint=f'{ODDS_URL}/sports/{sport}/events?'+urlencode({'apiKey':key})
                events,_=get_json(endpoint)
                if not isinstance(events,list):continue
                for m in games:
                    event=fixed_odds_event(m,events)
                    if event and event.get('id'):
                        matched.append((m,event,sport))
            except (HTTPError,URLError,ValueError,TimeoutError) as exc:
                issues.append(f'Arrangementer ({sport}): '+type(exc).__name__)
    matched.sort(key=lambda x:(x[0].get('kickoff') or '', x[0].get('league') or ''))
    cache={}
    # Strict small quota; cards and corners are optional, not worth emptying
    # free-plan credits and breaking matchwinner / goals odds.
    for m,e,sport in matched[:max(0,min(cap,2))]:
        if not key:break
        if remaining is not None and remaining<35:break
        query=urlencode({'apiKey':key,'regions':'eu',
                         'markets':'alternate_totals_corners,alternate_totals_cards',
                         'oddsFormat':'decimal'})
        try:
            result,remaining=get_json(f"{ODDS_URL}/sports/{sport}/events/{e['id']}/odds?{query}")
            budgets['odds_requests']+=1
            quotes=bookmaker_quotes(result or {},
                {'alternate_totals_corners','alternate_totals_cards'},at)
        except (HTTPError,URLError,ValueError,TimeoutError) as exc:
            issues.append('Kort/hjørnespark odds: '+type(exc).__name__)
            continue
        if not quotes:continue
        budgets['events']+=1
        home_stats,away_stats=load_history_for_fixture(m,stats_key,cache,issues)
        for code,q in quotes.items():
            kind='corners' if code.startswith('CO') else 'cards'
            counted[kind]+=1
            side='over' if code[2]=='O' else 'under'
            line=int(code[3:])/10
            p,sample=observed_probability(home_stats,away_stats,kind,line,side)
            # Can fall back to already derived corners model, only for exact lines.
            if p is None and kind=='corners':
                model=(m.get('model') or {}).get('probabilities') or {}
                legacy='CO'+f'{int(line*10):02d}'
                prior=model.get(legacy)
                if isinstance(prior,(int,float)) and .05<=prior<=.95:
                    p=prior if side=='over' else 1-prior
                    sample=8 # Existing v1.2 corner model internally requires >=8 matches.
            good=evaluate(q,p,kind,sample,at)
            reasons=[]
            if p is None:reasons.append('Mangler verifiserbar kort- eller hjørnesparkhistorikk')
            else:
                reasons.append(f'Siste registrerte kamper: minst {sample} per lag')
                reasons.append(f'Historisk frekvens: {p*100:.0f} % · oddsterskel: {100/q["price"]:.0f} %')
            reasons.append(f'Pris fra {q["books"]} bookmakere')
            pick={'matchId':m.get('id'),'home':m.get('home'),'away':m.get('away'),
                  'league':m.get('league'),'kickoff':m.get('kickoff'),
                  'market':code,'label':label(code),'marketType':kind,'price':q['price'],
                  'bookmakers':q['books'],'oddsUpdatedAt':q['lastUpdated'],
                  'probability':p,'verified':good,'rationale':reasons,
                  'source':'The Odds API','sampleSize':sample}
            (tips if good else watch).append(pick)
    # Optional extra team totals (including UNDER), both-teams-NO, and half goals.
    # Quote-only until sufficient independent match history is available.
    if matched and key and (remaining is None or remaining>=35):
        m,e,sport=matched[0]
        params=urlencode({'apiKey':key,'regions':'eu','markets':'team_totals,btts,totals_h1','oddsFormat':'decimal'})
        try:
            extra,remaining=get_json(f"{ODDS_URL}/sports/{sport}/events/{e['id']}/odds?{params}")
            budgets['odds_requests']+=1
            more=watch_special_goal_markets(m,extra or {},at)
            for option in more:
                counted[option['marketType']]+=1
            watch.extend(more)
        except (HTTPError,URLError,ValueError,TimeoutError) as exc:
            issues.append('Utvidede målmarkeder: '+type(exc).__name__)
    # Player props: US bookmaker coverage is limited to the major leagues.
    # The player and team must match unique, real season-scorer statistics.
    eligible=next(((m,e,s) for m,e,s in matched if s in LEAGUE_CODES),None)
    if eligible and key and (remaining is None or remaining>=35):
        m,e,sport=eligible
        query=urlencode({'apiKey':key,'regions':'us',
                         'markets':'player_goal_scorer_anytime','oddsFormat':'decimal'})
        try:
            result,remaining=get_json(f"{ODDS_URL}/sports/{sport}/events/{e['id']}/odds?{query}")
            budgets['odds_requests']+=1
            player_quotes=bookmaker_quotes(result or {},{'player_goal_scorer_anytime'},at)
        except (HTTPError,URLError,ValueError,TimeoutError) as exc:
            issues.append('Målscorerodds: '+type(exc).__name__);player_quotes={}
        scorers=[]
        if player_quotes and stats_key:
            try:
                result,_=get_json(f'{FD_URL}/competitions/{LEAGUE_CODES[sport]}/scorers?limit=60',
                                  {'X-Auth-Token':stats_key})
                scorers=result.get('scorers') or []
            except (HTTPError,URLError,ValueError,TimeoutError) as exc:
                issues.append('Målscorerhistorikk: '+type(exc).__name__)
        for code,q in list(player_quotes.items())[:14]:
            counted['goalscorer']+=1
            hist=scorer_probability(scorers,q['player'],m['home'],m['away'])
            p,n,goals=hist if hist else (None,0,0)
            good=evaluate(q,p,'goalscorer',n,at) if hist else False
            reasons=[f'Mål i ligaen: {goals} på {n} kamper' if hist else 'Mangler verifisert scorerhistorikk',
                     f'Pris fra {q["books"]} bookmakere',
                     'Startoppstilling må bekreftes før spill']
            # Morning lineup is unknown: scorer props are watch candidates only.
            watch.append({'matchId':m.get('id'),'home':m.get('home'),'away':m.get('away'),
                         'league':m.get('league'),'kickoff':m.get('kickoff'),
                         'market':code,'label':label(code,q['player']),
                         'marketType':'goalscorer','price':q['price'],'bookmakers':q['books'],
                         'oddsUpdatedAt':q['lastUpdated'],'probability':p,'verified':False,
                         'rationale':reasons,'source':'The Odds API','sampleSize':n,
                         'needsLineup':True,'statisticallyInteresting':good})
    # Keep the v1.2 goal, team and half-time markets discoverable.
    watch.extend(existing_market_watch(snapshot,at))
    # Dedup, ensure a single line has no contradictory recommendation.
    tips.sort(key=lambda x: (-(x['probability']*x['price']-1),-x['bookmakers']))
    tips=tips[:4]
    represented={(p['matchId'],p['market']) for p in tips}
    watch=[p for p in watch if (p['matchId'],p['market']) not in represented]
    # Represent diverse market families, not six variants of one popular game.
    priority={'goalscorer':0,'cards':1,'corners':2,'goals':3,'team_goals':4,'first_half':5,'btts':6}
    watch.sort(key=lambda x:(priority.get(x['marketType'],9),-x['bookmakers'],x['kickoff']))
    compact=[];seen=set()
    for p in watch:
        key=(p['matchId'],p['marketType'])
        if key in seen:continue
        seen.add(key);compact.append(p)
        if len(compact)>=8:break
    snapshot['additionalMarkets']={'tips':tips,'watchlist':compact,
        'coverage':{CATEGORY_NAMES.get(k,k):counted.get(k,0) for k in CATEGORY_NAMES},
        'issues':issues[:6], 'providerRequests':budgets['odds_requests'],
        'notes':'Kun verifiserte bookmakerpriser. For kort/hjørnespark kreves historiske data. Målscorer krever bekreftet startoppstilling.'}
    return snapshot


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('snapshot',type=Path)
    a=p.parse_args()
    if not a.snapshot.exists():raise SystemExit('Kandidatfil finnes ikke')
    original=json.loads(a.snapshot.read_text(encoding='utf8'))
    at=iso_datetime(original.get('generatedAt') or datetime.now(timezone.utc).isoformat())
    # No loss of core analysis if the optional scanner cannot fetch supplementary odds.
    try:
        updated=run(original,os.environ.get('ODDS_API_KEY','').strip(),
                    os.environ.get('FOOTBALL_DATA_API_KEY','').strip(),at,
                    cap=int(os.environ.get('ODDS_V14_EXTRA_EVENTS','1')))
    except Exception as exc:
        # Leave the original candidate intact: the daily update must keep working.
        print('WARNING additional markets not fetched:',type(exc).__name__,file=sys.stderr)
        return
    tmp=a.snapshot.with_name(a.snapshot.name+'.tmp')
    tmp.write_text(json.dumps(updated,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    tmp.replace(a.snapshot)
    print('V14_MARKETS tips='+str(len(updated['additionalMarkets']['tips']))+
          ' watch='+str(len(updated['additionalMarkets']['watchlist']))+
          ' requests='+str(updated['additionalMarkets']['providerRequests']))


if __name__=='__main__':main()
