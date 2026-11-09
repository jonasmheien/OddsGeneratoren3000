#!/usr/bin/env python3
"""Decide whether the scheduled GitHub Actions run should build tomorrow's preview.

No network requests, no betting-model changes and no bookmaker credits. The
caller changes mode from `results` to `tomorrow` once after the last displayed
kickoff, only if a preview for tomorrow hasn't already been published.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OSLO = ZoneInfo('Europe/Oslo')
ROOT = Path(__file__).resolve().parents[1]


def parse_dt(value):
    try:
        value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def read(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def visible_kickoffs(edition, now):
    """Only today's actually shown recommendations/observations determine rollover.

    Without shown tips, use bookmaker-backed games; if even those are absent,
    fall back to the Oslo evening cutoff so a blank day doesn't block tomorrow.
    """
    local_day = now.astimezone(OSLO).date()
    picks = []
    for section in ('recommendations', 'safeBets', 'highRisk', 'observations'):
        for item in edition.get(section) or []:
            if not isinstance(item, dict):
                continue
            kickoff = parse_dt(item.get('kickoff'))
            if kickoff and kickoff.astimezone(OSLO).date() == local_day:
                picks.append(kickoff)
    if picks:
        return picks
    for item in edition.get('matches') or []:
        if not isinstance(item, dict) or not item.get('odds'):
            continue
        kickoff = parse_dt(item.get('kickoff'))
        if kickoff and kickoff.astimezone(OSLO).date() == local_day:
            picks.append(kickoff)
    return picks


def is_due(active, preview, now, *, hourly=True):
    if not isinstance(active, dict) or now.tzinfo is None:
        return False
    local = now.astimezone(OSLO)
    day = local.date().isoformat()
    tomorrow = (local.date() + timedelta(days=1)).isoformat()
    if (active.get('editionDate') or active.get('localDate')) != day:
        return False
    if isinstance(preview, dict) and preview.get('previewEdition') is True and preview.get('editionDate') == tomorrow:
        return False
    # After midnight, the normal morning publication takes responsibility.
    # The hourly limit prevents repeated expensive data calls on API failures.
    if not 11 <= local.hour <= 23 or (hourly and local.minute > 8):
        return False
    starts = visible_kickoffs(active, now)
    if starts:
        return max(starts) <= now.astimezone(timezone.utc)
    return local.hour >= 18


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--due', action='store_true', help='Exit 0 only when a new preview should be built')
    p.add_argument('--broad-window', action='store_true',
                   help='Allow delayed scheduled preview dispatches without minute filtering')
    args = p.parse_args()
    active = read(ROOT / 'state' / 'active.json') or read(ROOT / 'site' / 'data' / 'today.json')
    preview = read(ROOT / 'site' / 'data' / 'tomorrow.json')
    due = is_due(active, preview, datetime.now(timezone.utc), hourly=not args.broad_window)
    print('ROLLOVER_TOMORROW_DUE=' + str(due).lower())
    if args.due:
        raise SystemExit(0 if due else 1)


if __name__ == '__main__':
    main()
