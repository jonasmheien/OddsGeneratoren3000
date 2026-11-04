"""Conservative football market screening. No guaranteed outcomes or calibrated ROI.

Selections require actual bookmaker quotes, sufficient historical scores, fresh
prices, and model-vs-market sanity checks. A market favourite is a probability
estimate, not a declaration of positive expected value.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from market_expansion import EXTRA_LABELS

MARKET_LABELS = {
    'H':'Hjemmeseier','U':'Uavgjort','B':'Borteseier',
    'O25':'Over 2,5 mål','U25':'Under 2,5 mål','O35':'Over 3,5 mål',
    'BTTS':'Begge lag scorer', **EXTRA_LABELS,
}
ALLOWED = tuple(k for k in MARKET_LABELS if k!='U')


def _time(value):
    if isinstance(value, datetime):return value
    return datetime.fromisoformat(str(value).replace('Z','+00:00'))


def valid_quote(odds, now, min_books=2):
    try:
        price,books=float(odds['price']),int(odds['books'])
        stamp=_time(odds['lastUpdated'])
    except (KeyError,ValueError,TypeError):return False
    age=(now-stamp).total_seconds()/3600
    return 1.05<=price<=25 and books>=min_books and -1<=age<=12


def market_favorite(match: dict, now: datetime) -> dict | None:
    """Safe section = priced favourite, never a guarantee or claimed edge."""
    try:
        kick=_time(match['kickoff'])
        if match.get('status') not in ('SCHEDULED','TIMED') or kick<=now+timedelta(minutes=10):return None
    except (KeyError,TypeError,ValueError):return None
    prices={}
    for code in ('H','U','B'):
        q=(match.get('odds') or {}).get(code) or {}
        if not valid_quote(q,now,min_books=3):return None
        prices[code]=(float(q['price']),int(q['books']),_time(q['lastUpdated']))
    implied={k:1/v[0] for k,v in prices.items()}
    margin=sum(implied.values())
    if not .98<=margin<=1.22:return None
    winner=min(('H','B'),key=lambda k:prices[k][0])
    if prices[winner][0]>1.60:return None
    fair_prob=implied[winner]/margin
    if fair_prob<.61:return None
    sample=(match.get('model') or {}).get('sample') or []
    if len(sample)!=2 or min(sample)<3:return None
    return {'market':winner, 'label':MARKET_LABELS[winner], 'category':'safe',
            'price':prices[winner][0],'probability':round(fair_prob,4),
            'probabilitySource':'market','modelEdge':None,
            'bookmakers':prices[winner][1], 'oddsSource':'The Odds API · bookmaker-median',
            'oddsUpdatedAt':prices[winner][2].isoformat(),
            'score':round(30+fair_prob*35+min(prices[winner][1],10)*.2,2),
            'formSample':list(sample),'evidenceLevel':'markedsfavoritt',
            'rationale':[f'Markedssjanse uten margin: {fair_prob*100:.0f} %',
                         f'Pris fra {prices[winner][1]} bookmakere',
                         'Favoritt er ikke det samme som positiv forventningsverdi'],
            'formHome':match.get('formHome') or '',
            'formAway':match.get('formAway') or '','externalSupport':0}


def _h2h_fair(match):
    raw=match.get('odds') or {}
    try:
        prices={k:float(raw[k]['price']) for k in ('H','U','B')}
    except (KeyError,TypeError,ValueError):return {}
    margin=sum(1/price for price in prices.values())
    if not .98<=margin<=1.22:return {}
    return {k:(1/v)/margin for k,v in prices.items()}


def analyze_match(match:dict,now:datetime)->list[dict]:
    if match.get('status') not in ('SCHEDULED','TIMED'):return []
    try:kick=_time(match['kickoff'])
    except (KeyError,ValueError,TypeError):return []
    if kick<=now+timedelta(minutes=10):return []
    m=match.get('model') or {}
    samples=m.get('sample') or []
    if len(samples)!=2 or min(samples)<3:
        fav=market_favorite(match,now)
        return [fav] if fav else []
    n=min(samples)
    if m.get('quality') not in ('basic','exploratory'):return []
    result=[]
    fair_market=_h2h_fair(match)
    for code in ALLOWED:
        q=(match.get('odds') or {}).get(code) or {}
        if not valid_quote(q,now):continue
        try:
            price,p,books=float(q['price']),float(m['probabilities'][code]),int(q['books'])
            age=(now-_time(q['lastUpdated'])).total_seconds()/3600
        except (KeyError,ValueError,TypeError):continue
        if not .08<=p<=.95:continue
        if code.startswith('H1') and n<5:continue
        # Corner probabilities are exposed only by the historical-statistics
        # estimator, which independently requires >=8 actual match records.
        # Remove the most notorious outliers. A large disagreement with the
        # bookmakers is not evidence that the simple model found a 200% edge.
        # In the absence of a complete H/D/A market, high-priced winners are
        # never recommended on this exploratory model alone.
        if code in ('H','B'):
            if price>4.0:continue
            if price>=2.25 and code in fair_market and abs(p-fair_market[code])>.13:continue
        # Value estimates from a six-game Poisson heuristic are not precise.
        # Penalize very large deviations from market-implied probability.
        implied=1/price
        if p-implied>(.28 if price<2.5 else .16):continue
        edge=p*price-1
        if price<=1.5:
            if n<5 or p<.70 or edge<.045:continue
            category='safe'
        elif 1.5<price<=1.80:
            if n<5 or p<.61 or edge<.025:continue
            category='safe'
        elif price>=1.85:
            if price>4.0 or p<.25 or edge<(.035 if n<5 else .065):continue
            category='high'
        else:
            if n<4 or p<.49 or edge<.05:continue
            category='standard'
        independent=[]
        for x in match.get('predictions',[]):
            v=(x.get('probabilities') or {}).get(code)
            if isinstance(v,(float,int)):independent.append((x.get('source','Ekstern modell'),float(v)))
        if any(v < p-.17 for _,v in independent):continue
        support=[name for name,v in independent if abs(v-p)<=.12 and v*price>=1]
        score=round(45*(min(edge,.25))+4*min(books,5)+2*min(n,6)+3*len(support)-.3*max(age,0),2)
        reasons=[f'Modellanslag: {p*100:.0f} % · nullpunkt: {100/price:.0f} %',
                 f'Form: {samples[0]} og {samples[1]} registrerte kamper',
                 f'Odds fra {books} bookmakere']
        if support:reasons.append('Bekreftende ekstern prognose: '+', '.join(support[:2]))
        else:reasons.append('Ingen uavhengig modellbekreftelse')
        result.append({'market':code,'label':MARKET_LABELS[code],
                       'category':category,'price':price,'probability':round(p,4),
                       'probabilitySource':'model','modelEdge':round(edge,4),
                       'bookmakers':books,'oddsSource':'The Odds API · bookmaker-median',
                       'oddsUpdatedAt':q['lastUpdated'],'score':score,
                       'formSample':list(samples),'evidenceLevel':'begrenset' if n<5 else 'standard',
                       'rationale':reasons,'formHome':match.get('formHome') or '',
                       'formAway':match.get('formAway') or '','externalSupport':len(support)})
    fav=market_favorite(match,now)
    if fav and not any(p['market']==fav['market'] and p['category']=='safe' for p in result):
        result.append(fav)
    return sorted(result,key=lambda x:x['score'],reverse=True)


def curated_picks(matches:list,now:datetime,limit:int=5)->list[dict]:
    picks=[]
    for m in matches:
        options=analyze_match(m,now)
        if options:
            best=options[0]
            picks.append({**best,'matchId':m.get('id'),'league':m.get('league'),
                          'home':m.get('home'),'away':m.get('away'),'kickoff':m.get('kickoff')})
    picks.sort(key=lambda p:(-p['score'],p['kickoff']))
    out=[];seen=set()
    for p in picks:
        if p['matchId'] not in seen:seen.add(p['matchId']);out.append(p)
        if len(out)>=limit:break
    return out


def category_picks(matches:list,now:datetime,category:str,limit:int=3)->list[dict]:
    picks=[]
    for m in matches:
        opts=[p for p in analyze_match(m,now) if p['category']==category]
        if opts:
            best=opts[0]
            picks.append({**best,'matchId':m.get('id'),'league':m.get('league'),
                          'home':m.get('home'),'away':m.get('away'),'kickoff':m.get('kickoff')})
    picks.sort(key=lambda p:(-p['score'],p['kickoff']))
    out=[];seen=set()
    for p in picks:
        if p['matchId'] not in seen:seen.add(p['matchId']);out.append(p)
        if len(out)>=limit:break
    return out
