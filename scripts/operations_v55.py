"""Persist real acquisition outcomes independently of the last valid edition.

Expected empty days, missing coverage and credit reserves are different from
provider failures. A failed refresh never replaces published tips or results.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from final_selection_v40 import OSLO, dt
from odds_budget_v55 import atomic_json, read_json

ROOT = Path(__file__).resolve().parents[1]


def classify(snapshot, now):
    status = snapshot.get('dataStatus') or {}
    coverage = snapshot.get('coverage') or {}
    discovery = status.get('matchdayDiscovery') or {}
    target = snapshot.get('localDate') or snapshot.get('editionDate')
    matches = snapshot.get('matches')
    if isinstance(matches, list):
        upcoming = [m for m in matches if (start := dt(m.get('kickoff'))) and start > now
                    and start.astimezone(OSLO).date().isoformat() == target]
        counts = {'upcoming': len(upcoming), 'withOdds': sum(bool(m.get('odds')) for m in upcoming),
                  'withModel': sum(bool(m.get('model')) for m in upcoming)}
    else:
        counts = {'upcoming': coverage.get('upcomingMatches', 0),
                  'withOdds': coverage.get('matchedOdds', 0), 'withModel': coverage.get('withModel', 0)}
    if (status.get('fixtures') in ('error', 'not_configured') or status.get('odds') in ('error', 'not_configured')
            or (not counts['withOdds'] and (status.get('oddsBudget') or {}).get('uncertainCredits'))):
        reason = 'source_error'
    elif status.get('oddsBudgetLimited') or (status.get('oddsBudget') or {}).get('denied'):
        reason = 'quota_limited'
    elif not counts['upcoming']:
        reason = 'no_fixtures'
    elif not counts['withOdds']:
        reason = 'coverage_limited' if discovery.get('catalogAvailable') and not status.get('requestedLeagues') else 'waiting_for_odds'
    elif not any(snapshot.get(category) for category in ('recommendations', 'safeBets', 'highRisk', 'interestingObjects')):
        reason = 'no_qualified_tips'
    else:
        reason = 'ready'
    return {'targetDate': target, 'reason': reason, 'coverage': counts,
            'providers': {'fixtures': status.get('fixtures'), 'odds': status.get('odds'),
                          'sportmonks': (status.get('sportmonks') or {}).get('state'),
                          'catalogAvailable': discovery.get('catalogAvailable'),
                          'failedEventLists': discovery.get('failedSports', 0),
                          'failedOddsRequests': status.get('failedOddsRequests', 0)},
            'requestedLeagues': status.get('requestedLeagues', []),
            'oddsCreditsRemaining': status.get('oddsCreditsRemaining'),
            'budget': status.get('oddsBudget')}


def record_attempt(root, snapshot, now, *, mode='core'):
    path = Path(root) / 'state/analysis-status-v55.json'
    journal = read_json(path) or {'schemaVersion': 55, 'attempts': {}}
    if journal.get('schemaVersion') != 55 or not isinstance(journal.get('attempts'), dict):
        raise ValueError('Unknown operational journal')
    journal['attempts'][mode] = dict(classify(snapshot, now), checkedAt=now.isoformat(),
                                     runId=os.getenv('GITHUB_RUN_ID'))
    atomic_json(path, journal)


def comparable(value):
    if isinstance(value, dict):
        return {key: comparable(item) for key, item in value.items() if key not in ('checkedAt', 'runId')}
    if isinstance(value, list):
        return [comparable(item) for item in value]
    return value


def publish(root=ROOT, now=None, *, mode='', analysis_failed=False, results_failed=False):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(OSLO).date().isoformat()
    journal = read_json(root / 'state/analysis-status-v55.json') or {}
    attempts = journal.get('attempts') or {}
    if analysis_failed:
        purpose = 'preview' if mode == 'tomorrow' else 'core'
        attempt = attempts.get(purpose) or {}
        if (attempt.get('runId') != os.getenv('GITHUB_RUN_ID') or
                attempt.get('reason') != 'source_error'):
            attempt = dict(attempt, reason='analysis_error', checkedAt=now.isoformat(),
                           targetDate=today if purpose == 'core' else attempt.get('targetDate'))
        attempts[purpose] = attempt
        atomic_json(root / 'state/analysis-status-v55.json', {'schemaVersion': 55, 'attempts': attempts})
    active = read_json(root / 'state/active.json') or read_json(root / 'site/data/today.json') or {}
    results = read_json(root / 'state/result-status-v55.json') or {'state': 'not_checked'}
    if results_failed:
        results = dict(results, state='unavailable', checkedAt=now.isoformat())
        atomic_json(root / 'state/result-status-v55.json', results)
    current = attempts.get('core') or {}
    reason = current.get('reason', 'not_checked') if current.get('targetDate') == today else 'not_checked'
    payload = {'schemaVersion': 55, 'checkedAt': now.isoformat(),
               'checkedHour': now.replace(minute=0, second=0, microsecond=0).isoformat(),
               'targetDate': today, 'reason': reason,
               'editionDate': active.get('editionDate') or active.get('localDate'),
               'editionGeneratedAt': active.get('generatedAt'),
               'lastAnalysis': attempts.get('core'), 'previewAnalysis': attempts.get('preview'),
               'results': results}
    path = root / 'site/data/operations-v55.json'
    changed = comparable(read_json(path)) != comparable(payload)
    if changed:
        atomic_json(path, payload)
    summary = os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as handle:
            handle.write('### Driftskontroll\n\n')
            handle.write(f'- Dagens analyse: `{reason}`\n')
            handle.write(f'- Publisert utgave: `{payload["editionDate"]}`\n')
            handle.write(f'- Resultatkontroll: `{results["state"]}`\n')
            if current.get('oddsCreditsRemaining') is not None:
                handle.write(f'- Odds-kreditter igjen: `{current["oddsCreditsRemaining"]}`\n')
    return {'changed': changed, 'reason': reason, 'results': results['state']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--mode', default=os.getenv('MODE', ''))
    args = parser.parse_args()
    result = publish(args.root, mode=args.mode,
                     analysis_failed=os.getenv('ANALYSIS_FAILED') == 'true',
                     results_failed=os.getenv('RESULTS_FAILED') == 'true')
    print('OPERATIONS_V55 ' + json.dumps(result, sort_keys=True))
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as handle:
            handle.write('changed=' + str(result['changed']).lower() + '\n')


if __name__ == '__main__':
    main()
