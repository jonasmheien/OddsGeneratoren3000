#!/usr/bin/env python3
"""Post-source v2.0 qualification pass for new candidate snapshots.

Run AFTER all optional market and score data enrichments, BEFORE lifecycle.py.
Only operates on a generated candidate. Never touches active editions or history.
No API calls, bets, purchases or bookmaker account access.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from quality_v20 import dt, family, fresh_quote, number, overlaps, ranking, screen, rejection_reason, reference_probability
from recommend import MARKET_LABELS


def _candidate(match, code, quote, metrics, label=None, kind=None):
    price = float(quote['price'])
    p = metrics['conservativeProbability']
    category = ('safe' if p >= .67 and price <= 1.85 else
                'high' if p < .48 or price >= 2.25 else 'standard')
    rationale = [
        f'Statistisk scenario: {metrics["conservativeProbability"]*100:.1f} % etter usikkerhetsjustering',
        f'Beregnet verdi i scenarioet: {metrics["conservativeEdge"]*100:+.1f} % (ikke historisk validert)',
        f'Nullpunkt i odds: {metrics["breakEvenOdds"]:.2f} · pris: {price:.2f}',
        f'Historiske resultater per lag: minst {metrics["sampleSize"]}' if kind != 'special' else
        f'Observerte data: minst {metrics["sampleSize"]} registreringer per lag',
        f'Pris fra {quote.get("books", quote.get("bookmakers"))} bookmaker(e); siste oppdatering kontrolleres',
    ]
    if metrics['externalDisagreements']:
        rationale.append('En eller flere eksterne prognoser er uenige. Usikkerheten er økt.')
    if metrics['referenceMethod'] == 'single_quote_break_even':
        rationale.append('Ingen komplett to-/treveis-pris for marginjustering; ekstra konservativ kontroll')
    return {
        'matchId':match.get('id'), 'home':match.get('home'),'away':match.get('away'),
        'league':match.get('league'),'kickoff':match.get('kickoff'),
        'homeCrest':match.get('homeCrest'), 'awayCrest':match.get('awayCrest'),
        'leagueCrest':match.get('leagueCrest'),
        'market':code, 'label':label or MARKET_LABELS.get(code,code),
        'marketType':family(code), 'category':category,'price':price,
        'bookmakers':quote.get('books',quote.get('bookmakers')),
        'oddsSource':'The Odds API · bookmaker-median',
        'oddsUpdatedAt':quote.get('lastUpdated',quote.get('oddsUpdatedAt')),
        'probability':metrics['rawProbability'],
        'modelEdge':metrics['conservativeEdge'],
        'score':round(metrics['conservativeEdge']*100,3),
        'probabilitySource':metrics['probabilitySource'],
        'evidenceLevel':'konservativt_scenario_ikke_validert',
        'formHome':match.get('formHome') or '', 'formAway':match.get('formAway') or '',
        'formSample':list((match.get('model') or {}).get('sample') or []),
        'rationale':rationale, 'externalSupport':0, **metrics,
    }


def qualify(snapshot):
    """Enforce qualification on all markets; do not perpetuate old safe favourites."""
    if not isinstance(snapshot, dict):
        raise ValueError('Invalid snapshot')
    when = dt(snapshot.get('generatedAt'))
    if not when:
        raise ValueError('Candidate has no valid generatedAt timestamp')
    matches = snapshot.get('matches')
    if not isinstance(matches, list):
        raise ValueError('Candidate has no matches array')
    by_id = {str(m.get('id')):m for m in matches if isinstance(m,dict) and m.get('id') is not None}
    options = []
    observed = []
    failures = Counter()

    def attempt(m, code, q, *, estimate=None, sample=None, kind='regular', label=None):
        if not fresh_quote(q,when):
            failures['manglende_eller_gamle_odds'] += 1
            return
        metrics = screen(m,code,when,estimate=estimate,sample=sample,kind=kind,
                         quote=q if kind=='special' else None)
        if metrics:
            options.append(_candidate(m,code,q,metrics,label,kind))
            return
        failures[rejection_reason(m, code, when, estimate=estimate, sample=sample, kind=kind, quote=q if kind=='special' else None)] += 1
        # Observations require an actual *statistical signal*, not merely odds.
        prob = number(estimate if estimate is not None else ((m.get('model') or {}).get('probabilities') or {}).get(code))
        price = number(q.get('price'))
        if prob is None or price is None or not (.07 <= prob <= .93) or prob * price - 1 < .04:
            return
        # Outliers can indicate mismatched opponents or an underpowered
        # Poisson estimate, not a giant betting opportunity.
        ref, _ = (reference_probability(code, m.get('odds') or {}, when) if kind != 'special'
                  else (1 / price, 'single_quote_break_even'))
        if ref is None or abs(prob - ref) > .22:
            return
        if m.get('status') not in ('SCHEDULED', 'TIMED') or not dt(m.get('kickoff')) or dt(m['kickoff']) <= when:
            return
        observed.append({'matchId':m.get('id'),'home':m.get('home'),'away':m.get('away'),
                         'league':m.get('league'),'kickoff':m.get('kickoff'),
                         'market':code,'marketType':family(code),
                         'label':label or MARKET_LABELS.get(code,code),
                         'price':price,'probability':round(prob,4),
                         'oddsUpdatedAt':q.get('lastUpdated',q.get('oddsUpdatedAt')),
                         'bookmakers':q.get('books',q.get('bookmakers')),
                         'status':'observation',
                         'reason':'Foreløpig statistisk signal, men usikkerhet eller datagrunnlag oppfyller ikke anbefalingskravene',
                         '_sort':prob * price - 1})

    # First consider all priced core markets, not only the previous top five.
    for m in matches:
        if not isinstance(m,dict):
            continue
        for code,q in (m.get('odds') or {}).items():
            if code not in MARKET_LABELS:
                continue
            attempt(m,code,q)

    # Upgrade special markets ONLY if they independently pass the new gate.
    # Special quotes are retained as observations/audit data otherwise.
    ext = snapshot.get('additionalMarkets') or {}
    for entry in (ext.get('tips') or []) + (ext.get('watchlist') or []):
        m = by_id.get(str(entry.get('matchId'))) if isinstance(entry,dict) else None
        if not m:
            continue
        code = str(entry.get('market') or '')
        if family(code) not in {'corners', 'cards', 'scorer', 'first_half', 'team_home','team_away','btts','goals'}:
            continue
        # A market's exact line/identity is never inferred from prose.
        if not code or code in (m.get('odds') or {}):
            continue
        q = {'price':entry.get('price'), 'books':entry.get('bookmakers'),
             'lastUpdated':entry.get('oddsUpdatedAt')}
        sample = entry.get('sampleSize')
        if type(sample) is not int:
            sample = 0
        attempt(m,code,q,estimate=entry.get('probability'),sample=sample,
                kind='special',label=entry.get('label'))

    # Each match may feature up to two meaningfully different markets.
    # Do not add opposite totals, redundant lines or highly overlapping legs.
    options.sort(key=ranking)
    chosen = []
    by_match = {}
    dedup = set()
    for p in options:
        mid = str(p.get('matchId'))
        key = (mid,p['market'])
        if key in dedup:
            continue
        dedup.add(key)
        same = by_match.setdefault(mid,[])
        if len(same) >= 2 or any(overlaps(p['market'],v['market']) for v in same):
            failures['overlappende_spill'] += 1
            continue
        chosen.append(p)
        same.append(p)

    # A chosen outcome's market family cannot simultaneously be an observation.
    active_families = {(str(p['matchId']), family(p['market'])) for p in chosen}
    observed.sort(key=lambda p:(-p['_sort'],str(p.get('kickoff') or '')))
    notes=[]
    noted=set()
    for p in observed:
        group=(str(p['matchId']),family(p['market']))
        if group in active_families or group in noted:
            continue
        noted.add(group)
        p.pop('_sort',None)
        notes.append(p)
        if len(notes)>=8:
            break

    snapshot['recommendations'] = chosen
    # The v2 UI uses category labels/filters on ONE list. Lifecycle settles the
    # entire recommendations list, without duplicating bets across categories.
    snapshot['safeBets'] = []
    snapshot['highRisk'] = []
    snapshot['observations'] = notes
    snapshot['modelVersion'] = '2.0-foundation'
    snapshot['qualityAudit'] = {
        'screened':len(options)+sum(failures.values()),
        'qualified':len(chosen), 'topLimit':5,
        'observations':len(notes), 'rejections':dict(failures),
        'calibrated':False,
        'method':'Eksplisitt sensitivitetsscenario, markedsforankring og usikkerhetstrekk; ikke validert som konfidensintervall',
        'coverageLimit':'Tilgjengelige kilde-/bookmakerodds, ikke alle globale markeder',
        'whyNoPicks':'Ingen tips bestod den usikkerhetsjusterte verdikontrollen. Se rejection-tall for årsaker.' if not chosen else None,
    }
    snapshot['qualityGate'] = {
        'minimumFormMatchesPerTeam':5, 'minimumSpecialStatisticsPerTeam':8,
        'maximumOddsAgeHours':6, 'oneBookmakerRequiresSamples':8,
        'minimumConservativeScenarioEdge':0.02,
        'explanation':'Ukalibrert sannsynlighetsmodell. Kun positiv forventet verdi i et konservativt scenario, ikke påvist langsiktig avkastning.'
    }
    if isinstance(snapshot.get('coverage'),dict):
        snapshot['coverage']['safeFound'] = sum(p['category']=='safe' for p in chosen)
        snapshot['coverage']['highFound'] = sum(p['category']=='high' for p in chosen)
        snapshot['coverage']['qualified'] = len(chosen)
    if isinstance(snapshot.get('dataStatus'),dict) and isinstance(snapshot['dataStatus'].get('analysisReadiness'),dict):
        snapshot['dataStatus']['analysisReadiness']['recommended'] = len(chosen)
    return snapshot


def main(path):
    target = Path(path)
    if not target.is_file() or target.name == 'active.json' or target.parent.name == 'data':
        raise SystemExit('Refuse to modify active/public snapshots; candidate path required')
    obj = json.loads(target.read_text(encoding='utf-8'))
    obj = qualify(obj)
    temp = target.with_name(target.name+'.v20.tmp')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(target)
    print('V20_QUALIFIED='+str(len(obj['recommendations']))+' OBSERVATIONS='+str(len(obj['observations'])))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python scripts/qualify_v20.py state/.candidate.json')
    main(sys.argv[1])
