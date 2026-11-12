"""Additional football markets with an actual price and observed form.

No corners/HT/team goals are fabricated. A missing bookmaker price or a missing
historical data field leaves that market unselectable. All probabilities are
exploratory and not calibrated for financial wagering.
"""
from __future__ import annotations
import math
from datetime import datetime

EXTRA_LABELS = {
    'O15':'Over 1,5 mål', 'U15':'Under 1,5 mål', 'U35':'Under 3,5 mål',
    'BTTSN':'Begge lag scorer: Nei',
    'H1O05':'1. omgang over 0,5 mål','H1O15':'1. omgang over 1,5 mål',
    'H1U15':'1. omgang under 1,5 mål',
    'CO85':'Over 8,5 hjørnespark', 'CO95':'Over 9,5 hjørnespark',
}
TEAM_TOTAL_LINES = (0.5, 1.5, 2.5)
for prefix, side in (('TH', 'Hjemmelaget'), ('TA', 'Bortelaget')):
    for line in TEAM_TOTAL_LINES:
        suffix = f'{int(line * 10):02d}'
        label = str(line).replace('.', ',')
        EXTRA_LABELS[f'{prefix}O{suffix}'] = f'{side} over {label} mål'
        EXTRA_LABELS[f'{prefix}U{suffix}'] = f'{side} under {label} mål'


def poisson_over(lam: float, threshold: float) -> float:
    # Asian lines intentionally excluded, only k+0.5 with unambiguous settlement.
    k=int(threshold)
    return max(0.0,min(1.0, 1 - sum(math.exp(-lam)*lam**i/math.factorial(i) for i in range(k+1))))


def extend_goal_probabilities(model: dict) -> None:
    if not model or not isinstance(model.get('expectedGoals'),list) or len(model['expectedGoals']) != 2:
        return
    lh,la=[float(v) for v in model['expectedGoals']]
    p=model.setdefault('probabilities',{})
    for code,lam,threshold in [('O15',lh+la,1.5),('U15',lh+la,1.5),('U35',lh+la,3.5)]:
        v=poisson_over(lam,threshold)
        if code.startswith('U'): v=1-v
        p[code]=round(v,4)
    if 'BTTS' in p:
        p['BTTSN'] = round(1 - p['BTTS'], 4)
    for prefix, rate in (('TH', lh), ('TA', la)):
        for line in TEAM_TOTAL_LINES:
            suffix = f'{int(line * 10):02d}'
            above = poisson_over(rate, line)
            p[f'{prefix}O{suffix}'] = round(above, 4)
            p[f'{prefix}U{suffix}'] = round(1 - above, 4)


def recent_half_form(fixtures: list, before: datetime, team_id: int, limit:int=6) -> list[tuple]:
    from build_data import iso_datetime
    values=[]
    for m in fixtures:
        if m.get('status')!='FINISHED':continue
        try:kick=iso_datetime(m['utcDate'])
        except (ValueError,KeyError,TypeError):continue
        if kick >= before:continue
        home=(m.get('homeTeam') or {}).get('id')
        away=(m.get('awayTeam') or {}).get('id')
        if team_id not in (home,away):continue
        halftime=(m.get('score') or {}).get('halfTime') or {}
        h,a=halftime.get('home'),halftime.get('away')
        if type(h) is not int or type(a) is not int:continue
        gf,ga=(h,a) if team_id==home else (a,h)
        values.append((kick,gf,ga))
    values.sort(reverse=True)
    return values[:limit]


def first_half_probabilities(fixtures:list, before:datetime, home_id:int, away_id:int):
    hf=recent_half_form(fixtures,before,home_id)
    af=recent_half_form(fixtures,before,away_id)
    if min(len(hf),len(af))<5:return {}
    def smooth(rows,index,prior):
        return (sum(x[index] for x in rows)+6*prior)/(len(rows)+6)
    # 0.7 home / 0.55 away first-half goals priors, heavily shrunk.
    home_lam=max(.2,min(2.2,(smooth(hf,1,.7)*smooth(af,2,.7))**.5))
    away_lam=max(.15,min(2.0,(smooth(af,1,.55)*smooth(hf,2,.55))**.5))
    total=home_lam+away_lam
    return {'H1O05':round(poisson_over(total,.5),4),
            'H1O15':round(poisson_over(total,1.5),4),
            'H1U15':round(1-poisson_over(total,1.5),4)}


def corner_probabilities(fixtures:list,before:datetime,home_id:int,away_id:int):
    """Enabled only when enough *actual* per-match corners exist in feed.

    The base football-data.org free plan generally does not provide these;
    this will correctly return {} rather than fabricate a corners estimate.
    """
    rows={home_id:[],away_id:[]}
    from build_data import iso_datetime
    for m in fixtures:
        if m.get('status')!='FINISHED':continue
        try:kick=iso_datetime(m['utcDate'])
        except (KeyError,TypeError,ValueError):continue
        if kick>=before:continue
        participants={side: (m.get(side+'Team') or {}) for side in ('home','away')}
        a=participants['home']; b=participants['away']
        if a.get('id') not in rows and b.get('id') not in rows:continue
        ha=(a.get('statistics') or {}).get('corner_kicks'); aa=(b.get('statistics') or {}).get('corner_kicks')
        if type(ha) is not int or type(aa) is not int or min(ha,aa)<0:continue
        for tid in rows:
            if tid in (a.get('id'),b.get('id')):
                rows[tid].append((kick,ha+aa))
    if min(len(rows[home_id]),len(rows[away_id]))<8:return {}
    selected=[sorted(rows[t],reverse=True)[:10] for t in (home_id,away_id)]
    # Smoothed empirical frequency from the observed last matches. Nontime-varying
    # priors are acknowledged; we require 8+ actual matches per side.
    result={}
    for code,number in [('CO85',9),('CO95',10)]:
        counted=sum(sum(1 for _,total in side if total>=number) for side in selected)
        total=sum(len(side) for side in selected)
        result[code]=round((counted+2.5)/(total+5),4)
    return result
