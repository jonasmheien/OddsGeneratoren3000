"""Risk-aware screening of *uncalibrated* football probability estimates.

This is a transparent sensitivity test, NOT a statistical confidence interval,
validated forecast, proven positive EV or financial recommendation.  It does
not invent bookmaker quotes, independent predictions or missing statistics.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from collections import Counter

MIN_EDGE = 0.02  # Margin after a deliberately pessimistic probability scenario.
MAX_AGE_HOURS = 6
COMPANIONS = {
    'O15':'U15','U15':'O15','O25':'U25','U25':'O25',
    'O35':'U35','U35':'O35','BTTS':'BTTSN','BTTSN':'BTTS',
    'H1O15':'H1U15','H1U15':'H1O15',
}


def dt(value):
    try:
        v = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if v.tzinfo is None:
            return None
        return v.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def number(value):
    try:
        # Avoid bool, nan and infinity, which silently poison rankings.
        if isinstance(value, bool):
            return None
        val = float(value)
        return val if math.isfinite(val) else None
    except (ValueError, TypeError, OverflowError):
        return None


def fresh_quote(q, now):
    if not isinstance(q, dict):
        return False
    p = number(q.get('price'))
    stamp = dt(q.get('lastUpdated') or q.get('oddsUpdatedAt'))
    books = number(q.get('books', q.get('bookmakers')))
    return bool(p is not None and 1.05 <= p <= 25 and stamp and books is not None
                and int(books) == books and books >= 1
                and -1 <= (now - stamp).total_seconds() / 3600 <= MAX_AGE_HOURS)


def reference_probability(code, odds, now):
    """De-vig a *complete* two- or three-way market; else use offered break-even.

    Median prices from multiple books are not executable joint prices; the
    normalized reference is only a model-sanity cross-check, not an arb quote.
    """
    if not isinstance(odds, dict):
        return None, 'missing'
    q = odds.get(code)
    if not fresh_quote(q, now):
        return None, 'stale'
    fair_keys = ('H', 'U', 'B') if code in ('H', 'U', 'B') else (code, COMPANIONS[code]) if code in COMPANIONS else ()
    if fair_keys and all(fresh_quote(odds.get(k), now) for k in fair_keys):
        inverses = {k: 1 / float(odds[k]['price']) for k in fair_keys}
        vig = sum(inverses.values())
        if 0.985 <= vig <= 1.25:
            return inverses[code] / vig, 'margin_normalized'
    return 1 / float(q['price']), 'single_quote_break_even'


def family(code):
    c = str(code)
    if c in ('H', 'B', 'U'):
        return 'winner'
    if c.startswith(('TH', 'TA')):
        return 'team_home' if c.startswith('TH') else 'team_away'
    if c.startswith('H1'):
        return 'first_half'
    if c.startswith(('CO',)):
        return 'corners'
    if c.startswith(('CA',)):
        return 'cards'
    if c.startswith(('GS:',)):
        return 'scorer'
    if c.startswith('BTTS'):
        return 'btts'
    if c.startswith(('O', 'U')):
        return 'goals'
    return 'other'


def overlaps(a, b):
    """Conservative overlap policy for multiple picks in the same match."""
    fa, fb = family(a), family(b)
    if fa == fb:
        return True
    if (fa == 'winner' and fb in {'team_home', 'team_away', 'btts'}) or (fb == 'winner' and fa in {'team_home', 'team_away', 'btts'}):
        return True
    if (fa == 'goals' and fb in {'btts', 'team_home', 'team_away', 'first_half'}) or (fb == 'goals' and fa in {'btts', 'team_home', 'team_away', 'first_half'}):
        return True
    return False


def assess(*, price, model_probability, market_probability, sample, books, age_hours,
           conflicting_sources=0, kind='regular'):
    """Return an explicit conservative *scenario*, or None if unsuitable.

    Shrink toward the offered market's break-even estimate, then apply a
    sample-size/quote-coverage cushion.  This is NOT a fitted uncertainty bound.
    """
    price, p, ref = number(price), number(model_probability), number(market_probability)
    if any(v is None for v in (price, p, ref)) or not (1.05 <= price <= 25 and .03 <= p <= .97 and .03 <= ref <= .97):
        return None
    if isinstance(sample, bool) or type(sample) is not int or sample < (8 if kind == 'special' else 5):
        return None
    if type(books) is not int or books < 1 or (books < 2 and sample < 8):
        return None
    if not 0 <= age_hours <= MAX_AGE_HOURS:
        return None
    # An enormous 'model edge' is more likely to be an identity/model issue.
    if abs(p - ref) > .22:
        return None
    # Shrink the uncalibrated forecast toward the contemporaneous market.
    model_weight = min(.75, .48 + .025 * (sample - 5))
    blended = ref + model_weight * (p - ref)
    uncertainty = .018 + .065 * math.sqrt(5 / sample)
    if books == 1:
        uncertainty += .025
    if age_hours >= 4:
        uncertainty += .015
    if conflicting_sources:
        uncertainty += min(.035, .015 * conflicting_sources)
    conservative = max(0.0, blended - uncertainty)
    edge = conservative * price - 1
    if edge < MIN_EDGE:
        return None
    return {'conservativeProbability': round(conservative, 4),
            'rawProbability': round(p, 4), 'marketReferenceProbability': round(ref, 4),
            'conservativeEdge': round(edge, 4),
            'breakEvenOdds': round(1 / conservative, 2),
            'scenarioPenalty': round(uncertainty, 4),
            'probabilitySource': 'uncalibrated_sensitivity_v20',
            'valueEvidence': 'foreløpig_estimat_ikke_validert'}


def screen(match, code, now, *, estimate=None, sample=None, kind='regular', quote=None):
    if match.get('status') not in ('SCHEDULED', 'TIMED'):
        return None
    kickoff = dt(match.get('kickoff'))
    if not kickoff or kickoff <= now + timedelta(minutes=10):
        return None
    odds = match.get('odds') or {}
    q = quote if quote is not None else odds.get(code)
    if not fresh_quote(q, now):
        return None
    model = match.get('model') or {}
    sizes = model.get('sample') or []
    if sample is None:
        if len(sizes) != 2 or not all(type(n) is int for n in sizes):
            return None
        sample = min(sizes)
        # Raw match count overstates confidence when most games are old.
        effective = model.get('effectiveSample')
        if (isinstance(effective, list) and len(effective) == 2 and
                all(number(v) is not None and number(v) >= 0 for v in effective)):
            sample = min(sample, int(min(effective)))
    if estimate is None:
        estimate = (model.get('probabilities') or {}).get(code)
    price = number(q.get('price'))
    age = (now - dt(q.get('lastUpdated') or q.get('oddsUpdatedAt'))).total_seconds() / 3600
    # If an external special quote is not part of the base match odds, the
    # reference is only that quote's break-even rate; no de-vig invented.
    ref, method = reference_probability(code, odds, now) if quote is None else (1 / price, 'single_quote_break_even')
    if ref is None:
        return None
    independent = []
    for pred in match.get('predictions') or []:
        p = number((pred.get('probabilities') or {}).get(code)) if isinstance(pred, dict) else None
        if p is not None and 0 <= p <= 1:
            independent.append(p)
    conflicts = sum(v < number(estimate) - .10 for v in independent) if number(estimate) is not None else 0
    books = int(q.get('books', q.get('bookmakers')))
    metrics = assess(price=price, model_probability=estimate, market_probability=ref,
                     sample=sample, books=books, age_hours=max(0.0, age),
                     conflicting_sources=conflicts, kind=kind)
    if not metrics:
        return None
    if model.get('quality') not in ('basic', 'exploratory') and kind == 'regular':
        return None
    return {**metrics, 'referenceMethod':method, 'sampleSize':sample,
            'externalDisagreements':conflicts, 'sourceAgeHours':round(max(0, age), 2)}


def ranking(pick):
    return (-float(pick['conservativeEdge']), str(pick.get('kickoff') or ''), str(pick.get('matchId') or ''))


def rejection_reason(match, code, now, *, estimate=None, sample=None, kind='regular', quote=None):
    """Diagnostic only; never overrides the actual quality decision."""
    if match.get('status') not in ('SCHEDULED', 'TIMED'):
        return 'kamp_ikke_kommende'
    kickoff = dt(match.get('kickoff'))
    if not kickoff or kickoff <= now + timedelta(minutes=10):
        return 'kamp_startet_eller_snart_start'
    odds = match.get('odds') or {}
    q = quote if quote is not None else odds.get(code)
    if not fresh_quote(q, now):
        return 'manglende_eller_gamle_odds'
    model = match.get('model') or {}
    sizes = model.get('sample') or []
    if sample is None:
        if len(sizes) != 2 or not all(type(n) is int for n in sizes):
            return 'manglende_kamphistorikk'
        sample = min(sizes)
        effective = model.get('effectiveSample')
        if isinstance(effective, list) and len(effective) == 2 and all(number(v) is not None for v in effective):
            sample = min(sample, int(min(effective)))
    if sample < (8 if kind == 'special' else 5):
        return 'for_lite_historikk'
    if estimate is None:
        estimate = (model.get('probabilities') or {}).get(code)
    p = number(estimate)
    if p is None or not .03 <= p <= .97:
        return 'manglende_eller_usannsynlig_modellestimat'
    price = number(q.get('price'))
    if price is None or not 1.05 <= price <= 25:
        return 'ugyldige_odds'
    ref, _ = reference_probability(code, odds, now) if quote is None else (1 / price, 'single_quote_break_even')
    if ref is None or not .03 <= ref <= .97:
        return 'manglende_markedsreferanse'
    if abs(p - ref) > .22:
        return 'stort_modell_marked_avvik'
    books = number(q.get('books', q.get('bookmakers')))
    if books is None or (books < 2 and sample < 8):
        return 'svak_bookmakerdekning'
    return 'for_lav_konservativ_verdi'
