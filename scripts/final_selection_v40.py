"""Authoritative, conflict-free selection for OddsGeneratoren3000 v40.

No API calls. Consumes the completed v20 qualification snapshot. No invented
prices or outcomes. At most one active selection per real fixture across all
three categories: a deliberate conservative guard against both logical
contradictions and ambiguous cross-market correlations.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

OSLO = ZoneInfo('Europe/Oslo')
ALIASES = {
    'hsv': 'hamburgersv', 'hamburgsv': 'hamburgersv',
    'mgladbach': 'monchengladbach',
    'borussiamgladbach': 'monchengladbach',
    'borussiamonchengladbach': 'monchengladbach',
    'bmonchengladbach': 'monchengladbach',
    'boltonwanderers': 'bolton', 'silkeborgif': 'silkeborg',
    'fczwolle': 'zwolle', 'peczwolle': 'zwolle', 'sevillafc': 'sevilla',
}
LABELS = {
    'H': 'Hjemmeseier', 'U': 'Uavgjort', 'B': 'Borteseier',
    'BTTS': 'Begge lag scorer: Ja', 'BTTSN': 'Begge lag scorer: Nei',
}

def dt(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (TypeError, ValueError, OverflowError):
        return None

def club(name):
    s = unicodedata.normalize('NFKD', str(name or '')).lower()
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = ''.join(c for c in s if c.isascii() and c.isalnum())
    return ALIASES.get(s, s)

def fixture_key(p):
    kickoff = dt(p.get('kickoff'))
    home, away = club(p.get('home')), club(p.get('away'))
    if not kickoff or not home or not away:
        return None
    # The local day + ordered team identities bridge independent provider IDs.
    # We intentionally avoid fuzzy matching unrelated clubs.
    return f'{kickoff.astimezone(OSLO).date()}|{home}|{away}'

def market_identity(code):
    """Typed, settlement-specific identity. Never infer the line from the label."""
    c = str(code or '').upper()
    if c in ('H', 'U', 'B'):
        return dict(family='match_result', period='full_time', line=None,
                    subject=None, outcome={'H':'home','U':'draw','B':'away'}[c])
    if c in ('BTTS', 'BTTSN'):
        return dict(family='btts',period='full_time',line=None,subject=None,
                    outcome='yes' if c == 'BTTS' else 'no')
    if c.startswith('GS:') and len(c)>3:
        return dict(family='anytime_scorer',period='full_time',line=None,
                    subject=c[3:].lower(),outcome='yes')
    for pattern, family, period, subject in (
        (r'^([OU])(\d{2,3})$', 'total_goals', 'full_time', None),
        (r'^H1([OU])(\d{2,3})$', 'total_goals', 'first_half', None),
        (r'^TH([OU])(\d{2,3})$', 'team_goals', 'full_time', 'home'),
        (r'^TA([OU])(\d{2,3})$', 'team_goals', 'full_time', 'away'),
        (r'^CO([OU])(\d{2,3})$', 'corners', 'full_time', None),
        (r'^CA([OU])(\d{2,3})$', 'cards', 'full_time', None),
    ):
        m = re.fullmatch(pattern,c)
        if m:
            line = int(m.group(2))/10
            if abs(line % 1 - .5) > 1e-9:
                return None  # No guessed Asian-line settlements.
            return dict(family=family,period=period,line=line,subject=subject,
                        outcome='over' if m.group(1)=='O' else 'under')
    return None

def market_label(code):
    if code in LABELS: return LABELS[code]
    i=market_identity(code)
    if not i:return None
    if i['family']=='anytime_scorer':return None  # Keep supplied actual player name.
    line=str(i['line']).replace('.',',')
    verb='Over' if i['outcome']=='over' else 'Under'
    if i['family']=='total_goals':
        return ('1. omgang ' if i['period']=='first_half' else '')+f'{verb.lower() if i["period"]=="first_half" else verb} {line} mål'
    if i['family']=='team_goals':
        return f'{"Hjemmelaget" if i["subject"]=="home" else "Bortelaget"} {verb.lower()} {line} mål'
    return f'{verb} {line} {"kort" if i["family"]=="cards" else "hjørnespark"}'

def quote(q, now, min_books=3, max_age=12):
    if not isinstance(q,dict):return False
    try:
        odds=float(q.get('price'))
        books=int(q.get('books',q.get('bookmakers')))
        stamped=dt(q.get('lastUpdated',q.get('oddsUpdatedAt')))
        age=(now-stamped).total_seconds()/3600 if stamped else 1e6
        return 1.05<=odds<=25 and books>=min_books and -2/60<=age<=max_age
    except (TypeError,ValueError,OverflowError):return False

def fair(m, code, now):
    if code in ('H','B','U'): codes=['H','U','B']
    elif code[:1] in ('O','U') and code[1:].isdigit():codes=['O'+code[1:],'U'+code[1:]]
    else:return None
    odds=m.get('odds') or {}
    if not all(quote(odds.get(k),now) for k in codes):return None
    vals={k:1/float(odds[k]['price']) for k in codes}
    vig=sum(vals.values())
    return vals[code]/vig if .98<=vig<=1.27 else None

def _number(v):
    try:
        if v is None or v=='':return None
        n=float(v)
        return n if n==n and abs(n)!=float('inf') else None
    except (TypeError,ValueError):return None

def _base(m, code, q, tier, category, chance, reasons, strength):
    identity=market_identity(code)
    if not identity:return None
    actual_name=(m.get('home'),m.get('away'))
    selection={
        'matchId':m.get('id'),'home':actual_name[0],'away':actual_name[1],
        'kickoff':m.get('kickoff'),'league':m.get('league') or 'Fotball',
        'market':code,'marketType':identity['family'],
        'label':market_label(code),'price':float(q['price']),
        'bookmakers':int(q.get('books',q.get('bookmakers'))),
        'oddsUpdatedAt':q.get('lastUpdated',q.get('oddsUpdatedAt')),
        'oddsSource':q.get('source') or 'The Odds API',
        'probability':round(chance,4) if chance is not None else None,
        'category':category, 'qualificationTier':tier,
        '_candidateType':'market' if tier=='market' else ('model' if tier=='model' else None),
        'rationale':reasons,
        'fixtureKey':fixture_key(m),'marketIdentity':identity,
        '_selectionStrength':strength,
    }
    if code.startswith('GS:'):selection['label']=None
    return selection

def _candidates(snapshot, now):
    out=[]
    day=str(snapshot.get('editionDate') or snapshot.get('localDate') or '')
    matches=[m for m in (snapshot.get('matches') or []) if isinstance(m,dict) and fixture_key(m) and
             dt(m.get('kickoff')).astimezone(OSLO).date().isoformat()==day and
             dt(m.get('kickoff'))>now and m.get('status') in ('SCHEDULED','TIMED',None)]
    by_id={str(m.get('id')):m for m in matches}
    trace=[]
    for p in snapshot.get('recommendations') or []:
        if not isinstance(p,dict):continue
        m=by_id.get(str(p.get('matchId')))
        if not m or not market_identity(p.get('market')):continue
        if _number(p.get('conservativeEdge')) is None or _number(p['conservativeEdge'])<.02:continue
        if not quote({'price':p.get('price'),'books':p.get('bookmakers'),
                      'lastUpdated':p.get('oddsUpdatedAt')},now,min_books=1,max_age=6):continue
        cat=p.get('category')
        if cat not in ('safe','high'):
            # Standard outcomes have neither the Safe nor the High Risk criteria.
            trace.append({'market':p.get('market'),'fixture':fixture_key(m),'reason':'outside_category'})
            continue
        ident=market_identity(p['market'])
        obj={**p,'marketIdentity':ident,'fixtureKey':fixture_key(m),
             'qualificationTier':'qualified','_selectionStrength':100+
             min(15,float(p['conservativeEdge'])*30)+min(10,int(p.get('bookmakers') or 0))*.1}
        out.append((cat,obj))
    for m in matches:
        model=m.get('model') or {}
        probs=model.get('probabilities') or {}
        odds=m.get('odds') or {}
        sample=model.get('sample') or []
        es=model.get('effectiveSample') or []
        support=(len(sample)==2 and all(type(s) is int and s>=5 for s in sample)
                 and (len(es)!=2 or all(_number(s) is not None and float(s)>=4 for s in es)))
        for code in ['H','B','O25','U25','O35','U35','O15','U15']:
            q=odds.get(code)
            if not quote(q,now):continue
            price=_number(q.get('price'))
            if price is None:continue
            ref=fair(m,code,now)
            if ref is None:continue
            model_p=_number(probs.get(code))
            books=int(q.get('books',q.get('bookmakers')))
            # Safe: conservative bookmaker-backed short-price candidates. Never
            # describe these as a model-proven positive-edge bet.
            if 1.14<=price<=1.70 and ref>=.58 and (model_p is None or model_p>=ref-.16):
                reasons=[f'Markedsbasert kandidat: omtrent {ref*100:.0f} % etter bookmaker-marginkorreksjon.',
                         f'Pris fra {books} bookmakere. Ikke dokumentert spillverdi.']
                obj=_base(m,code,q,'market','safe',ref,reasons,15+ref*10+min(books,10)*.1)
                if obj:out.append(('safe',obj))
            # High risk: must have real quoted prices. Evidence-backed model
            # candidates are ranked above bookmaker-only longshots.
            if 2.2<=price<=8 and support and model_p is not None and .20<=model_p<=.75 and abs(model_p-ref)<=.20 and model_p>=ref+.015:
                reasons=[f'Modellkandidat: {model_p*100:.0f} % formanslag mot {ref*100:.0f} % fra bookmakerodds.',
                         'Ikke historisk kalibrert eller godkjent som dokumentert verdiobjekt.']
                obj=_base(m,code,q,'model','high',model_p,reasons,45+(model_p-ref)*25+min(books,15)*.1)
                if obj:out.append(('high',obj))
            elif 2.2<=price<=5.5 and books>=5 and .18<=ref<=.47 and (model_p is None or model_p>=ref-.12):
                reasons=[f'Bookmakerbasert risikokandidat: markedsanslag rundt {ref*100:.0f} %.',
                         'Ingen dokumentert positiv spillverdi.']
                obj=_base(m,code,q,'market','high',ref,reasons,12+ref*10+min(books,15)*.1)
                if obj:out.append(('high',obj))
    # Observations must originate from a real prior statistical signal, not
    # arbitrary market quotes. Review/watchlist can remain in the separate radar.
    for p in snapshot.get('observations') or []:
        if not isinstance(p,dict):continue
        m=by_id.get(str(p.get('matchId')))
        if not m or not market_identity(p.get('market')):continue
        if not quote({'price':p.get('price'),'books':p.get('bookmakers'),
                      'lastUpdated':p.get('oddsUpdatedAt')},now,min_books=2):continue
        obj={**p,'marketIdentity':market_identity(p['market']),
             'fixtureKey':fixture_key(m),'qualificationTier':'observation',
             '_selectionStrength':5+max(0,(_number(p.get('probability')) or 0)*10)}
        out.append(('watch',obj))
    return out,trace

def finalize(snapshot, now=None):
    """Create the sole three-section output. Never overwrite original raw evidence."""
    at=now or dt(snapshot.get('generatedAt'))
    if not at:raise ValueError('Missing generatedAt')
    if not isinstance(snapshot.get('matches'),list):raise ValueError('Missing matches')
    candidates,trace=_candidates(snapshot,at)
    # Qualified > supported model > bookmaker-only > statistical observation.
    # Within equal tiers, prefer documented strength and stable IDs.
    tier={'qualified':0,'model':1,'market':2,'observation':3}
    candidates.sort(key=lambda cp:(tier[cp[1]['qualificationTier']],
                -float(cp[1].get('_selectionStrength') or 0),
                str(cp[1].get('kickoff')),str(cp[1].get('matchId')),str(cp[1].get('market'))))
    groups={'safe':[],'high':[],'watch':[]}
    occupied={}
    blocked=Counter()
    for category,p in candidates:
        identity=p['fixtureKey']
        if identity in occupied:
            blocked['same_fixture_or_correlated_outcome']+=1
            trace.append({'fixture':identity,'market':p['market'],'reason':'same_fixture_or_correlated_outcome',
                          'selectedMarket':occupied[identity]['market']})
            continue
        if len(groups[category])>=5:
            blocked['category_full']+=1
            continue
        # Strip sorting/internal fields. Preserve identity and original quote.
        selection={k:v for k,v in p.items() if k!='_selectionStrength'}
        token=f'{identity}|{p["marketIdentity"]}'
        selection['selectionId']='v40:'+hashlib.sha256(token.encode()).hexdigest()[:20]
        groups[category].append(selection)
        occupied[identity]=selection
        trace.append({'fixture':identity,'selectionId':selection['selectionId'],
                      'market':selection['market'],'group':category,'reason':'selected'})
    snapshot['safeBets']=groups['safe']
    snapshot['highRisk']=groups['high']
    snapshot['interestingObjects']=groups['watch']
    # Other UI sections and results processing may show recommendations. Only
    # the qualified picks in the final selected categories belong there.
    snapshot['recommendations']=[p for g in ('safe','high') for p in groups[g]
                                 if p['qualificationTier']=='qualified']
    snapshot['finalSelection']={'version':40,'policy':'one_active_selection_per_real_fixture',
        'categories':{'safe':len(groups['safe']),'high':len(groups['high']),
                      'watch':len(groups['watch'])},
        'target':[3,5],'shortfalls':{g:('For få konfliktfrie, kildebaserte kandidater.' if len(v)<3 else None)
                                   for g,v in groups.items()},
        'rejected':dict(blocked),'trace':trace}
    if isinstance(snapshot.get('coverage'),dict):
        snapshot['coverage'].update(safeFound=len(groups['safe']),highFound=len(groups['high']))
    validate(snapshot)
    return snapshot

def validate(snapshot):
    """Fail closed if backend JSON contains conflicting final selections."""
    if not isinstance(snapshot.get('finalSelection'),dict) or snapshot['finalSelection'].get('version')!=40:
        raise ValueError('Missing authoritative v40 finalSelection')
    seen=set();ids=set()
    for name in ('safeBets','highRisk','interestingObjects'):
        picks=snapshot.get(name)
        if not isinstance(picks,list) or len(picks)>5:
            raise ValueError('Invalid final selection list: '+name)
        for p in picks:
            k=fixture_key(p)
            m=market_identity(p.get('market'))
            if not k or not m or p.get('fixtureKey')!=k or p.get('marketIdentity')!=m:
                raise ValueError('Malformed fixture/market identity')
            if k in seen:raise ValueError('Conflicting or correlated selections for fixture '+k)
            if p.get('selectionId') in ids:raise ValueError('Repeated selectionId')
            if not isinstance(p.get('price'),(int,float)) or p['price']<=1:
                raise ValueError('Invalid selection price')
            seen.add(k);ids.add(p.get('selectionId'))
    qualified={p['selectionId'] for g in ('safeBets','highRisk') for p in snapshot[g]
               if p.get('qualificationTier')=='qualified'}
    if {p.get('selectionId') for p in snapshot.get('recommendations',[])}!=qualified:
        raise ValueError('Recommendations disagree with final selection')
    return True
