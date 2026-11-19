"""First-publication policy shared by selection and historical reporting.

Never choose a historical record by its result. Original audit revisions and
ledger records remain intact; the public projection uses one record per match.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from final_selection_v40 import dt
from result_sources_v51 import selection_key

MAIN_GROUPS = ('safe', 'high', 'watch')


def fixture_identity(pick):
    key = selection_key(pick)
    return key.rsplit('|', 1)[0] if key else None


def display_category(group, pick, groups=None):
    if group in MAIN_GROUPS:
        return group
    # Earlier journals sometimes stored the same qualified pick in a main
    # category too. Prefer that recorded category over a price-based mapping.
    if groups:
        key = selection_key(pick)
        for category in MAIN_GROUPS:
            if any(selection_key(p) == key for p in groups.get(category) or []):
                return category
    return 'safe' if pick['price'] <= 1.85 else 'high' if pick['price'] >= 2.25 else 'watch'


def first_records(records):
    """A stable first record per real fixture, independent of win/loss status."""
    selected = {}
    for record in sorted(records, key=lambda p: (
            dt(p['firstPublishedAt']), str(p.get('publicationRevision', '')),
            str(p.get('selectionKey') or selection_key(p)), str(p.get('id', '')))):
        identity = fixture_identity(record)
        if identity:
            selected.setdefault(identity, record)
    return list(selected.values())


def publication_locks(root, now):
    """Read only genuine, pre-kickoff publications, including evening previews."""
    root = Path(root)
    records = []
    for path in sorted((root / 'state/tip-audit-v34').glob('????-??-??.json')):
        journal = json.loads(path.read_text(encoding='utf-8'))
        if journal.get('schemaVersion') != 34:
            raise ValueError('Unknown publication journal')
        for revision in journal.get('revisions') or []:
            recorded = dt(revision.get('recordedAt'))
            if not recorded or recorded > now:
                continue
            groups = revision.get('groups') or {}
            for group in (*MAIN_GROUPS, 'qualified'):
                for pick in groups.get(group) or []:
                    kickoff = dt(pick.get('kickoff'))
                    if (not kickoff or recorded >= kickoff or not fixture_identity(pick)
                            or type(pick.get('price')) not in (int, float) or not 1 < pick['price'] < 100):
                        continue
                    records.append(dict(pick, category=display_category(group, pick, groups),
                                        firstPublishedAt=recorded.isoformat(),
                                        publicationRevision=revision.get('id', '')))
    # Keep the policy effective if old audit files are absent from a checkout.
    ledger_path = root / 'state/hitrate-v51.json'
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
        if ledger.get('schemaVersion') != 51 or not isinstance(ledger.get('records'), list):
            raise ValueError('Unknown hit-rate journal')
        for record in ledger['records']:
            recorded, kickoff = dt(record.get('firstPublishedAt')), dt(record.get('kickoff'))
            if recorded and kickoff and recorded <= now and recorded < kickoff:
                records.append(dict(record, category=record.get('displayCategory') or
                                    display_category(record['category'], record)))
    return {fixture_identity(p): p for p in first_records(records)}


def lock_edition(snapshot, root, published_at=None):
    """Recheck publication locks at each publishing boundary, without API calls."""
    if (snapshot.get('finalSelection') or {}).get('version') == 40:
        from final_selection_v40 import finalize
        now = dt(snapshot.get('generatedAt'))
        if not now:
            raise ValueError('Missing analysis time')
        cutoff = published_at or datetime.now(timezone.utc)
        return finalize(snapshot, now, publication_locks=publication_locks(root, cutoff))
    return snapshot
