#!/usr/bin/env python3
"""Run a fresh morning analysis even when a preliminary same-day edition exists.

The first eligible morning schedule refreshes; later schedules are fallback only.
This avoids quota consumption from repeated fresh bookmaker calls.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OSLO = ZoneInfo('Europe/Oslo')
ROOT = Path(__file__).resolve().parents[1]


def should_refresh(edition, now):
    if now.tzinfo is None:
        raise ValueError('Timezone-aware datetime required')
    local = now.astimezone(OSLO)
    if not 9 <= local.hour <= 11:
        return False
    today = local.date().isoformat()
    if not isinstance(edition, dict) or (edition.get('editionDate') or edition.get('localDate')) != today:
        return True
    try:
        generated = datetime.fromisoformat(str(edition['generatedAt']).replace('Z', '+00:00'))
    except (KeyError, ValueError, TypeError):
        return True
    if generated.tzinfo is None:
        return True
    stamp = generated.astimezone(OSLO)
    # A snapshot created at 08:08 must NOT suppress the scheduled 09:17 edition.
    return stamp.date().isoformat() != today or (stamp.hour, stamp.minute) < (9, 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--due', action='store_true')
    args = parser.parse_args()
    edition = None
    for p in (ROOT / 'state' / 'active.json', ROOT / 'site' / 'data' / 'today.json'):
        try:
            obj = json.loads(p.read_text(encoding='utf-8'))
            if isinstance(obj, dict):
                edition = obj
                break
        except (OSError, ValueError):
            continue
    due = should_refresh(edition, datetime.now(timezone.utc))
    print('MORNING_REFRESH_DUE=' + str(due).lower())
    if args.due:
        raise SystemExit(0 if due else 1)

if __name__ == '__main__':
    main()
