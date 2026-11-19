#!/usr/bin/env python3
"""Lifetime hit rate of tips actually captured in the shared visibility journal.

The first publication fixes the category and price. Refreshes, removed tips,
provider ID changes and category moves cannot rewrite the denominator. Only
verified final results count as wins/losses; pending, unknown and void do not.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lifecycle import CATEGORIES, apply_results, atomic_json, fetch_results, published_history, read_json, score_pick
from result_sources_v51 import dt, match_saved_picks, selection_key
from publication_policy_v53 import display_category, first_records

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_NAMES = {'safe': 'Safe Bets', 'high': 'High Risk',
                  'watch': 'Interessante objekter'}
FINAL = {'won', 'lost', 'void'}


def publications(root):
    """Use recorded pre-kickoff visibility, never reconstruct tips from results."""
    entries = []
    for path in sorted((root / 'state/tip-audit-v34').glob('????-??-??.json')):
        journal = read_json(path)
        if not isinstance(journal, dict) or journal.get('schemaVersion') != 34:
            continue
        for revision in journal.get('revisions') or []:
            recorded = dt(revision.get('recordedAt'))
            if recorded is None:
                continue
            groups = revision.get('groups') or {}
            for group in ('safe', 'high', 'watch', 'qualified'):
                for pick in (revision.get('groups') or {}).get(group) or []:
                    kickoff = dt(pick.get('kickoff'))
                    if (not kickoff or recorded >= kickoff or not selection_key(pick)
                            or not pick.get('matchId') or type(pick.get('price')) not in (int, float)
                            or not 1 < pick['price'] < 100):
                        continue
                    category = display_category(group, pick, groups)
                    entries.append((recorded, category, journal.get('editionDate'), revision.get('id'), pick))
    return sorted(entries, key=lambda row: (row[0], ('safe', 'high', 'watch').index(row[1])))


def ingest(ledger, entries, now):
    by_key = {record['selectionKey']: record for record in ledger['records']}
    for recorded, group, day, revision, pick in entries:
        if recorded > now:
            continue
        key = selection_key(pick)
        record = by_key.get(key)
        if record is None:
            record = {field: deepcopy(pick.get(field)) for field in
                      ('matchId', 'home', 'away', 'league', 'kickoff', 'market', 'label', 'price')}
            record.update(id=hashlib.sha256(key.encode()).hexdigest()[:24], selectionKey=key,
                          category=group, editionDate=day, firstPublishedAt=recorded.isoformat(),
                          publicationRevision=revision, sourceIds=[], result={'status': 'scheduled'})
            by_key[key] = record
            ledger['records'].append(record)
        mid = str(pick['matchId'])
        if mid not in record['sourceIds']:
            record['sourceIds'].append(mid)
        if record['category'] == 'qualified' and not record.get('displayCategory'):
            record['displayCategory'] = group
    for record in ledger['records']:
        if (record['result'].get('status') not in FINAL | {'postponed', 'unverified'}
                and (kickoff := dt(record.get('kickoff'))) and now > kickoff + timedelta(hours=3)):
            record['result'] = {'status': 'unverified'}
    ledger['records'].sort(key=lambda record: (record['firstPublishedAt'], record['id']))


def count(records):
    statuses = [(p.get('result') or {}).get('status') for p in records]
    wins, losses = statuses.count('won'), statuses.count('lost')
    decided = wins + losses
    return {'total': len(statuses), 'wins': wins, 'losses': losses,
            'settled': decided, 'voids': statuses.count('void'),
            'unverified': statuses.count('unverified'),
            'pending': sum(s not in FINAL | {'unverified'} for s in statuses),
            'hitRatePct': round(100 * wins / decided, 1) if decided else None}


def report(ledger, now, feed):
    # Keep the complete journal. Exclude later alternatives by publication time,
    # including when the first tip lost and a later alternative won.
    records = [dict(p, category=p.get('displayCategory') or display_category(p['category'], p))
               for p in first_records(ledger['records'])]
    by_category = {key: dict(label=label, **count([p for p in records if p['category'] == key]))
                   for key, label in CATEGORY_NAMES.items()}
    dates = sorted({p['editionDate'] for p in records if p.get('editionDate')}, reverse=True)
    return {
        'schemaVersion': 51, 'generatedAt': now.isoformat(),
        'trackedFrom': min((p['firstPublishedAt'] for p in records), default=None),
        'overall': count(records), 'categories': by_category,
        'days': [{'date': day, 'categories': {
            key: count([p for p in records if p['editionDate'] == day and p['category'] == key])
            for key in CATEGORY_NAMES}} for day in dates],
        'tips': [{field: deepcopy(p.get(field)) for field in (
            'id', 'editionDate', 'category', 'home', 'away', 'kickoff', 'market',
            'label', 'price', 'firstPublishedAt', 'result')}
                 for p in reversed(records)],
        'resultFeed': feed,
        'publicationPolicy': {'version': 53, 'rule': 'first_published_tip_per_fixture',
                              'excludedAlternatives': len(ledger['records']) - len(records)},
        'method': 'Første publiserte tips per kamp. Vunnet / (vunnet + tapt).',
        'note': 'Kun avgjorte tips inngår i treffprosenten.',
    }


def write_if_changed(path, value, ignored=()):
    old = read_json(path)
    comparable = lambda obj: {k: v for k, v in obj.items() if k not in ignored} if isinstance(obj, dict) else obj
    if comparable(old) == comparable(value):
        return False
    atomic_json(path, value)
    return True


def sync(root=ROOT, now=None, *, fetcher=fetch_results, offline=False):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Timezone-aware clock required')
    location = root / 'state/hitrate-v51.json'
    existing = read_json(location)
    ledger = existing if existing is not None else {'schemaVersion': 51, 'records': []}
    if not isinstance(ledger, dict) or ledger.get('schemaVersion') != 51 or not isinstance(ledger.get('records'), list):
        raise ValueError('Unknown hit-rate journal; refusing to replace it')
    ingest(ledger, publications(root), now)
    due = [record for record in ledger['records'] if record['result'].get('status') not in FINAL
           and (start := dt(record.get('kickoff'))) and start < now]
    recent = [record for record in due if dt(record['kickoff']) >= now - timedelta(days=7)]
    old = [record for record in due if record not in recent
           and record.get('lastHistoricalCheckDay') != now.date().isoformat()]
    old_days = sorted({record['editionDate'] for record in old})[:2]
    batches = [recent] + [[record for record in old if record['editionDate'] == day] for day in old_days]
    batches = [batch for batch in batches if batch]
    rows = []
    feed = {'state': 'idle'}
    if batches and not offline:
        feed = {'state': 'checked'}
        for batch in batches:
            candidate = {'editionDate': min(p['editionDate'] for p in batch),
                         'recommendations': [dict(record, matchId=mid) for record in batch for mid in record['sourceIds']]}
            try:
                rows.extend(fetcher(candidate, os.getenv('FOOTBALL_DATA_API_KEY', '').strip()))
            except (OSError, ValueError, RuntimeError) as exc:
                feed = {'state': 'unavailable', 'error': type(exc).__name__}
                print('WARN: hit-rate results unavailable:', type(exc).__name__)
            for record in batch:
                if record not in recent:
                    record['lastHistoricalCheckDay'] = now.date().isoformat()
        feed['matchedFixtures'] = len(rows)
    elif offline:
        feed = {'state': 'not_checked'}
    for record in ledger['records']:
        if record['result'].get('status') in FINAL:
            continue
        aliases = [dict(record, matchId=mid) for mid in record['sourceIds']]
        matches = match_saved_picks(aliases, rows)
        if not matches:
            continue
        result = score_pick(record, matches[0])['result']
        if result['status'] == 'scheduled' and record['result'].get('status') == 'unverified':
            continue
        if result != record['result']:
            record['result'] = result
            if result['status'] in FINAL:
                record['settledAt'] = now.isoformat()

    # Reconcile the public edition and historical result copies with the same
    # official rows. Immutable publication/version journals stay unchanged.
    edition_changed = False
    cached_results = {record['selectionKey']: record['result'] for record in ledger['records']
                      if record['result'].get('status') in FINAL}
    paths = [root / 'state/active.json', *sorted((root / 'state/history').glob('????-??-??.json'))]
    for path in paths:
        edition = read_json(path)
        if not isinstance(edition, dict):
            continue
        picks = [p for category in CATEGORIES for p in edition.get(category) or []]
        matches = match_saved_picks(picks, rows)
        revised, changed = apply_results(edition, matches, at=now.isoformat())
        for category in CATEGORIES:
            for saved in revised.get(category) or []:
                cached = cached_results.get(selection_key(saved))
                if cached and (saved.get('result') or {}).get('status') not in FINAL:
                    saved['result'] = deepcopy(cached)
                    changed = True
        if changed:
            revised['resultUpdatedAt'] = now.isoformat()
            atomic_json(path, revised)
            edition_changed = True
            if path.name == 'active.json':
                atomic_json(root / 'site/data/today.json', revised)
    if edition_changed:
        active = read_json(root / 'state/active.json')
        atomic_json(root / 'site/data/history.json', published_history(active, root=root))
    journal_changed = write_if_changed(location, ledger)
    public = report(ledger, now, feed)
    # Operational request counts are deliberately not used to trigger new
    # deployments when the actual results have not changed.
    public_changed = write_if_changed(root / 'site/data/hitrate-v51.json', public,
                                      ignored=('generatedAt', 'resultFeed'))
    return {'changed': public_changed or edition_changed, 'journalChanged': journal_changed,
            'overall': public['overall'], 'categories': public['categories']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    result = sync(args.root, offline=args.offline)
    print('HITRATE_V51 ' + json.dumps(result, ensure_ascii=False, sort_keys=True))
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write('changed=' + str(result['changed']).lower() + '\n')


if __name__ == '__main__':
    main()
