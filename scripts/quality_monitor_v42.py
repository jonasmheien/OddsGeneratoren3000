#!/usr/bin/env python3
"""Read-only operational transparency for OddsGeneratoren3000.

Creates public diagnostics from already published, non-sensitive JSON files.
Never downloads odds, recomputes picks, guesses closing prices, or promotes tips.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OSLO = ZoneInfo('Europe/Oslo')
SETTLED = {'won', 'lost', 'void'}


def parsedate(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d if d.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError, OSError):
        return None


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def _finite(value):
    try:
        if isinstance(value, bool):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def quality_report(edition, now):
    """Explain *source coverage*, not fabricate a model-quality score."""
    if not isinstance(edition, dict):
        edition = {}
    coverage = edition.get('coverage') or {}
    status = edition.get('dataStatus') or {}
    bridge = status.get('officialFormBridge') or {}
    day = str(edition.get('editionDate') or edition.get('localDate') or '')
    generated = parsedate(edition.get('generatedAt'))
    today = now.astimezone(OSLO).date().isoformat()
    upcoming = int(coverage.get('upcomingMatches') or 0)
    matched = int(coverage.get('matchedOdds') or 0)
    linked = int(bridge.get('oddsFixturesWithBothTeamsMatched') or 0)
    external = int(status.get('externalPredictionsCount') or coverage.get('externalPredictions') or 0)
    age_hours = round(max(0, (now - generated).total_seconds()) / 3600, 2) if generated else None
    freshness = 'current' if day == today else ('not_published' if not day or day < today else 'future')
    # Before the first expected morning run, an older edition is normal.
    issues = []
    if freshness == 'not_published' and now.astimezone(OSLO).hour >= 10:
        issues.append('Ingen dagsutgave publisert for i dag')
    if day == today and age_hours is not None and age_hours > 8:
        issues.append('Dagens analyse er mer enn åtte timer gammel')
    if upcoming and matched / upcoming < .5:
        issues.append('Bookmakerodds er koblet til færre enn halvparten av kampene')
    if matched and linked == 0:
        issues.append('Ingen odds-kamper har fullstendig koblet ekstern laghistorikk')
    if external == 0:
        issues.append('Ingen eksterne prognoser er koblet til analysen')
    return {
        'schemaVersion': 42,
        'editionDate': day or None,
        'editionGeneratedAt': edition.get('generatedAt'),
        'checkedAt': now.isoformat(),
        'freshness': freshness,
        'analysisAgeHours': age_hours,
        'data': {
            'upcomingMatches': upcoming,
            'matchesWithOdds': matched,
            'oddsCoveragePct': round(100 * matched / upcoming, 1) if upcoming else None,
            'withModel': int(coverage.get('withModel') or 0),
            'oddsFixturesWithLinkedForm': linked,
            'externalPredictions': external,
            'qualifiedRecommendations': int(coverage.get('qualified') or 0),
            'safeBets': len(edition.get('safeBets') or []),
            'highRisk': len(edition.get('highRisk') or []),
            'interestingObjects': len(edition.get('interestingObjects') or []),
            'oddsCreditsRemaining': status.get('oddsCreditsRemaining'),
        },
        'issues': issues,
        'note': 'Dekning og kildetilgang er ikke et mål på historisk kalibrering, avkastning eller positiv forventet verdi.',
    }


def performance_report(history, now):
    """One-unit flat stake; only settled, non-duplicated historical outcomes.

    The public history contains no verified closing-line market prices. CLV is
    therefore intentionally unavailable instead of being inferred from EV.
    """
    if not isinstance(history, list):
        history = []
    dedup = {}
    for day in history:
        if not isinstance(day, dict):
            continue
        date = str(day.get('date') or day.get('editionDate') or '')
        if not date:
            continue
        for p in day.get('picks') or []:
            if not isinstance(p, dict) or p.get('status') not in SETTLED:
                continue
            price = _finite(p.get('price'))
            if p.get('status') != 'void' and (price is None or not 1.01 < price <= 100):
                continue
            if p.get('matchId') is None or not p.get('market'):
                continue
            key = (date, str(p['matchId']), str(p['market']))
            dedup.setdefault(key, (p['status'], price))
    outcomes = list(dedup.values())
    wins = sum(s == 'won' for s, _ in outcomes)
    losses = sum(s == 'lost' for s, _ in outcomes)
    voids = sum(s == 'void' for s, _ in outcomes)
    staked = wins + losses
    profit = sum((price - 1 if s == 'won' else -1 if s == 'lost' else 0) for s, price in outcomes)
    roi = round(100 * profit / staked, 1) if staked else None
    return {
        'schemaVersion': 42, 'generatedAt': now.isoformat(),
        'sample': {'settled': len(outcomes), 'wins': wins, 'losses': losses, 'voids': voids},
        'flatStake': {'unit': 1, 'totalStaked': staked, 'profitUnits': round(profit, 2),
                      'roiPct': roi, 'winRatePct': round(100 * wins / staked, 1) if staked else None},
        'insufficientSample': staked < 100,
        'closingLineValue': {'available': False, 'reason': 'Verifiserte sluttodds lagres ikke i dagens historikk'},
        'calibration': {'available': False, 'reason': 'Historikken lagrer ikke konsekvent modellens opprinnelige prognoser'},
        'note': 'Et lite historisk utvalg viser bare faktisk utfall. Avkastning dokumenterer ikke fremtidig verdi.',
    }


def prune_preview(path, edition, now):
    """Remove only outdated preview data. Never touch a valid future preview."""
    preview = read_json(path)
    if not isinstance(preview, dict) or preview.get('previewEdition') is not True:
        return False
    preview_day = str(preview.get('editionDate') or preview.get('localDate') or '')
    active_day = str(edition.get('editionDate') or edition.get('localDate') or '') if isinstance(edition, dict) else ''
    local_today = now.astimezone(OSLO).date().isoformat()
    if preview_day and (preview_day < local_today or (active_day and preview_day <= active_day)):
        Path(path).unlink(missing_ok=True)
        return True
    return False


def publish(root, now=None):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Time must be timezone-aware')
    active = read_json(root/'site/data/today.json')
    history = read_json(root/'site/data/history.json')
    data = root/'site/data'
    quality = quality_report(active, now)
    performance = performance_report(history, now)
    write_json(data/'quality-v42.json', quality)
    write_json(data/'performance-v42.json', performance)
    pruned = prune_preview(data/'tomorrow.json', active, now)
    return {'editionDate': quality['editionDate'], 'freshness': quality['freshness'],
            'settled': performance['sample']['settled'], 'prunedStalePreview': pruned}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(publish(args.root), ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
