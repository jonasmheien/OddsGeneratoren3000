#!/usr/bin/env python3
"""Read-only, transparent diagnostic of actually published, settled selections.

No scraping, API spend, or mutation of user snapshots.  A positive small-sample
ROI does not prove forecast calibration or a repeatable edge.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from quality_v20 import family, number


def evaluate(snapshots):
    picked={}
    for snap in snapshots:
        if not isinstance(snap,dict):
            continue
        day=snap.get('editionDate') or snap.get('localDate')
        if not day:
            continue
        for key in ('recommendations','safeBets','highRisk'):
            for p in snap.get(key) or []:
                if not isinstance(p,dict) or p.get('matchId') is None or not p.get('market'):
                    continue
                ident=(str(day),str(p['matchId']),str(p['market']))
                previous=picked.get(ident)
                if previous is None or (previous.get('result') or {}).get('status') not in ('won','lost'):
                    picked[ident]=p
    rows=[]
    for p in picked.values():
        status=(p.get('result') or {}).get('status')
        price=number(p.get('price'))
        if status not in ('won','lost') or price is None or not (1.01<price<=100):
            continue
        result=int(status=='won')
        row={'market':family(p['market']),'price':price,'win':result,
             'return':price-1 if result else -1}
        probability=number(p.get('probability'))
        if probability is not None and 0<=probability<=1:
            row['brier']=(probability-result)**2
        rows.append(row)
    def aggregate(values):
        n=len(values)
        return {'settled':n,'wins':sum(p['win'] for p in values),
                'winRate':round(sum(p['win'] for p in values)/n,4) if n else None,
                'flatStakeROI':round(sum(p['return'] for p in values)/n,4) if n else None,
                'rawProbabilityBrier':round(sum(p['brier'] for p in values if 'brier' in p)/sum('brier' in p for p in values),4) if any('brier' in p for p in values) else None,
                'insufficientSample':n<100}
    return {'overall':aggregate(rows),
            'byMarket':{k:aggregate([p for p in rows if p['market']==k]) for k in sorted(set(p['market'] for p in rows))},
            'warning':'Observasjonsbasert, ikke kontrollert for utvelgelsesbias. Positive tall alene beviser ingen framtidig verdi.'}


def main(root):
    snapshots=[]
    for path in sorted((root/'state'/'history').glob('????-??-??.json')):
        try:
            snapshots.append(json.loads(path.read_text(encoding='utf-8')))
        except (OSError,ValueError):
            continue
    active=root/'state'/'active.json'
    if active.exists():
        snapshots.append(json.loads(active.read_text(encoding='utf-8')))
    print(json.dumps(evaluate(snapshots),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main(Path(__file__).resolve().parents[1])
