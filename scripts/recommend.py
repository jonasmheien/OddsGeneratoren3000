"""Conservative, transparent screening for a personal football research dashboard.

IMPORTANT: This is an uncalibrated statistical heuristic, not betting advice.
Never force a minimum number of picks; empty output is a valid success state.
"""
from __future__ import annotations
from datetime import datetime, timedelta

MARKET_LABELS = {
    'H':'Hjemmeseier','U':'Uavgjort','B':'Borteseier',
    'O25':'Over 2,5 mål','U25':'Under 2,5 mål','O35':'Over 3,5 mål',
    'BTTS':'Begge lag scorer',
}
# Avoid drawing strong conclusions on draw probabilities from the simple baseline.
ALLOWED = ('H', 'B', 'O25', 'U25', 'O35', 'BTTS')


def _time(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace('Z','+00:00'))


def market_favorite(match: dict, now: datetime) -> dict | None:
    """Identify a clearly priced market favorite independently of the
    uncalibrated model. Not a claim of positive expected value.
    """
    try:
        kickoff=_time(match['kickoff'])
        if match.get('status') not in ('SCHEDULED','TIMED') or kickoff<=now+timedelta(minutes=10):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    prices={}
    for code in ('H','U','B'):
        q=(match.get('odds') or {}).get(code) or {}
        try:
            price=float(q['price'])
            books=int(q['books'])
            stamp=_time(q['lastUpdated'])
        except (ValueError, TypeError, KeyError):
            return None
        age=(now-stamp).total_seconds()/3600
        if not (1.01<=price<=50 and books>=3 and -1<=age<=12):
            return None
        prices[code]=(price,books,stamp)
    implied={code:1/val[0] for code,val in prices.items()}
    margin=sum(implied.values())
    # A clearly inconsistent/misordered market should not be interpreted.
    if not .98<=margin<=1.22:
        return None
    winner=min(('H','B'),key=lambda k:prices[k][0])
    if prices[winner][0]>1.60:
        return None
    fair_prob=implied[winner]/margin
    if fair_prob<.61:
        return None
    model=match.get('model') or {}
    sample=model.get('sample') or []
    if len(sample)!=2 or min(sample)<3:
        return None
    # A market favorite is not necessarily a good-value bet; the site shows
    # where its probability came from rather than attributing it to the model.
    return {'market':winner, 'label':MARKET_LABELS[winner], 'category':'safe',
            'price':prices[winner][0], 'probability':round(fair_prob,4),
            'probabilitySource':'market', 'modelEdge':None,
            'bookmakers':prices[winner][1], 'oddsSource':'The Odds API · bookmaker-median',
            'oddsUpdatedAt':prices[winner][2].isoformat(),
            'score':round(30+fair_prob*35+min(prices[winner][1],10)*.2,2),
            'formSample':list(sample),
            'evidenceLevel':'markedsfavoritt',
            'rationale':[f'Markedssjanse uten bookmaker-margin: {fair_prob*100:.0f} %',
                         f'Odds fra {prices[winner][1]} bookmakere',
                         'Ikke dokumentert positiv forventningsverdi'],
            'formHome':match.get('formHome') or '',
            'formAway':match.get('formAway') or '', 'externalSupport':0}


def analyze_match(match: dict, now: datetime) -> list[dict]:
    """Return eligible selections ordered by rank; may be empty."""
    if match.get('status') not in ('SCHEDULED','TIMED'):
        return []
    try:
        kickoff = _time(match['kickoff'])
    except (KeyError, ValueError, TypeError):
        return []
    if kickoff <= now + timedelta(minutes=10):
        return []
    m = match.get('model') or {}
    samples = m.get('sample') or []
    if len(samples)!=2 or min(samples)<3:
        # With limited team history, only a sufficiently supported bookmaker
        # favorite may appear; never create a Poisson-based recommendation.
        fav=market_favorite(match,now)
        return [fav] if fav else []
    sample_size=min(samples)
    # Limited form is allowed only for clearly marked high-risk ideas.
    # Safe bets and regular tips retain their stricter sample requirements.
    if m.get('quality') not in ('basic', 'exploratory'):
        return []
    choices=[]
    for code in ALLOWED:
        odds = (match.get('odds') or {}).get(code) or {}
        try:
            price, p, books = float(odds['price']), float(m['probabilities'][code]), int(odds['books'])
        except (TypeError,ValueError,KeyError):
            continue
        if books < 2 or not 1.05 <= price <= 20 or not 0.05 <= p <= 0.95:
            continue
        # Stale quotes are excluded rather than presenting old odds as current.
        stamp=odds.get('lastUpdated')
        if not stamp:
            continue
        try:
            age_hours=(now-_time(stamp)).total_seconds()/3600
        except (ValueError,TypeError):
            continue
        if age_hours < -1 or age_hours > 12:
            continue
        edge = p*price-1
        if price<=1.5:
            if sample_size<5 or p < .70 or edge < .045:
                continue
            category='safe'
        elif price>=1.85:
            # High risk can use 3-4 completed games on either side,
            # but needs at least two independent bookmaker quotes.
            min_edge=.035 if sample_size<5 else .085
            if p < .23 or edge < min_edge:
                continue
            category='high'
        else:
            if sample_size<4 or p < .49 or edge < .065:
                continue
            category='standard'
        # A manually recorded independent external model may support or oppose the baseline.
        independent=[]
        for x in match.get('predictions',[]):
            v=(x.get('probabilities') or {}).get(code)
            if isinstance(v,(float,int)):
                independent.append((x.get('source','Ekstern modell'),float(v)))
        conflict=any(v < p-.17 for _,v in independent)
        if conflict:
            continue
        supporting=[name for name,v in independent if abs(v-p)<=.12 and v*price >= 1.0]
        # Rank is an ordering heuristic, not a predictive score or calibrated certainty.
        score = round(100*edge + min(books,5)*1.2 + min(samples)*0.5 + len(supporting)*4 - min(age_hours,12)*0.4, 2)
        formh=match.get('formHome') or ''
        forma=match.get('formAway') or ''
        reasons=[f'Modell: {p*100:.0f} % · nullpunkt: {100/price:.0f} %',
                 f'Formgrunnlag: {samples[0]} og {samples[1]} kamper',
                 f'Pris fra {books} bookmakere']
        if supporting:
            reasons.append('Liknende prognose: '+', '.join(supporting[:2]))
        else:
            reasons.append('Ingen uavhengig modellbekreftelse registrert')
        choices.append({'market':code,'label':MARKET_LABELS[code], 'category':category,
                        'price':price,'probability':round(p,4), 'probabilitySource':'model', 'modelEdge':round(edge,4),
                        'bookmakers':books,'oddsSource':'The Odds API · bookmaker-median',
                        'oddsUpdatedAt':stamp,'score':score,
                        'formSample':list(samples),
                        'evidenceLevel':'begrenset' if sample_size<5 else 'standard',
                        'rationale':reasons,
                        'formHome':formh,'formAway':forma,'externalSupport':len(supporting)})
    fav=market_favorite(match,now)
    if fav and not any(x['market']==fav['market'] and x['category']=='safe' for x in choices):
        choices.append(fav)
    return sorted(choices,key=lambda x:x['score'],reverse=True)


def curated_picks(matches: list[dict], now: datetime, limit: int=5) -> list[dict]:
    """Zero to limit suggestions, with at most one market per match."""
    # Caller filters by Europe/Oslo day; kickoff guard still applies.
    per_match=[]
    for m in matches:
        options=analyze_match(m,now)
        if options:
            x={**options[0], 'matchId':m.get('id'),'league':m.get('league'),
               'home':m.get('home'),'away':m.get('away'),'kickoff':m.get('kickoff')}
            per_match.append(x)
    per_match.sort(key=lambda x:(-x['score'],x['kickoff']))
    result=[]
    seen=set()
    for item in per_match:
        if item['matchId'] in seen:
            continue
        seen.add(item['matchId'])
        result.append(item)
        if len(result)>=limit:
            break
    return result


def category_picks(matches: list[dict], now: datetime, category: str, limit: int=3) -> list[dict]:
    """Independently select category picks without being shadowed by a
    higher ranking selection of another category for the same fixture.
    """
    choices=[]
    for m in matches:
        opts=[p for p in analyze_match(m, now) if p['category']==category]
        if not opts:
            continue
        best=opts[0]
        choices.append({**best, 'matchId':m.get('id'), 'league':m.get('league'),
                        'home':m.get('home'), 'away':m.get('away'), 'kickoff':m.get('kickoff')})
    choices.sort(key=lambda x:(-x['score'],x['kickoff']))
    seen=set(); result=[]
    for p in choices:
        if p['matchId'] in seen:continue
        seen.add(p['matchId'])
        result.append(p)
        if len(result)>=limit:break
    return result
