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
        return []
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
                        'price':price,'probability':round(p,4), 'modelEdge':round(edge,4),
                        'bookmakers':books,'oddsSource':'The Odds API · bookmaker-median',
                        'oddsUpdatedAt':stamp,'score':score,
                        'formSample':list(samples),
                        'evidenceLevel':'begrenset' if sample_size<5 else 'standard',
                        'rationale':reasons,
                        'formHome':formh,'formAway':forma,'externalSupport':len(supporting)})
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
