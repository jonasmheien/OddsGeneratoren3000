#!/usr/bin/env python3
"""Publish a *preview* of tomorrow's recommendations without changing today's edition.

The next-day snapshot contains only data genuinely supplied by configured feeds.
The regular morning daily workflow remains authoritative for the next day's edition.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OSLO = ZoneInfo('Europe/Oslo')
ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / 'site' / 'data' / 'tomorrow.json'


def validate_preview(snapshot: dict, now: datetime) -> dict:
    """Reject an invalid preview without touching the active snapshot."""
    if now.tzinfo is None:
        raise ValueError('Current time must have a timezone')
    if not isinstance(snapshot, dict):
        raise ValueError('Invalid preview JSON')
    expected = (now.astimezone(OSLO).date() + timedelta(days=1)).isoformat()
    if snapshot.get('localDate') != expected:
        raise ValueError(f'Wrong preview date: expected {expected}, got {snapshot.get("localDate")}')
    if (snapshot.get('dataStatus') or {}).get('fixtures') != 'ok':
        raise ValueError('Match feed did not succeed')
    if (snapshot.get('dataStatus') or {}).get('odds') != 'ok':
        raise ValueError('Odds feed did not succeed')
    coverage = snapshot.get('coverage') or {}
    if int(coverage.get('matchedOdds') or 0) < 1:
        raise ValueError('No matching, independently sourced bookmaker odds for tomorrow')
    if not isinstance(snapshot.get('matches'), list) or not isinstance(snapshot.get('recommendations'), list):
        raise ValueError('Missing matches or recommendations')
    for pick in snapshot['recommendations']:
        if not isinstance(pick, dict) or not pick.get('kickoff') or not pick.get('market'):
            raise ValueError('Invalid recommended pick')
    preview = dict(snapshot)
    preview['previewEdition'] = True
    preview['editionDate'] = expected
    preview['editionLocked'] = False
    preview['previewNote'] = ('Forhåndsanalyse med tilgjengelige odds. '
                              'Ny kontroll utføres ved ordinær analyse neste morgen.')
    return preview


def publish_preview(snapshot: dict, now: datetime, destination: Path = PREVIEW) -> Path:
    preview = validate_preview(snapshot, now)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.tmp')
    temporary.write_text(json.dumps(preview, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description='Write tomorrow\'s standalone preview')
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    if not args.candidate.is_file():
        raise SystemExit('No candidate snapshot available')
    snapshot = json.loads(args.candidate.read_text(encoding='utf-8'))
    now = datetime.now(timezone.utc)
    status = snapshot.get('dataStatus') or {}
    coverage = snapshot.get('coverage') or {}
    expected = (now.astimezone(OSLO).date() + timedelta(days=1)).isoformat()
    if (snapshot.get('localDate') == expected and status.get('fixtures') == 'ok'
            and status.get('odds') in ('ok', 'empty')
            and isinstance(snapshot.get('matches'), list)
            and isinstance(snapshot.get('recommendations'), list)
            and int(coverage.get('matchedOdds') or 0) == 0):
        args.candidate.unlink(missing_ok=True)
        print('TOMORROW_PREVIEW_SKIPPED=no_bookmaker_odds_on_target_day')
        return
    published = publish_preview(snapshot, now)
    args.candidate.unlink(missing_ok=True)
    print('TOMORROW_PREVIEW_CREATED=' + str(snapshot.get('localDate')))
    print('QUALIFIED=' + str(len(snapshot.get('recommendations') or [])))
    print('MATCHED_ODDS=' + str((snapshot.get('coverage') or {}).get('matchedOdds') or 0))
    print('PREVIEW_FILE=' + str(published.relative_to(ROOT)))


if __name__ == '__main__':
    main()
