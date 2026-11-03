#!/usr/bin/env python3
"""Preserve each daily edition and settle its picks without repricing them.

The repository branch is the durable store on GitHub Actions. `state/active.json`
contains the selected morning edition. `site/data/today.json` is its public copy.
No API keys or account data are written to either file.
"""
from __future__ import annotations
import argparse
import json
import os
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'state' / 'active.json'
PUBLIC = ROOT / 'site' / 'data' / 'today.json'
HISTORY = ROOT / 'state' / 'history'
CATEGORIES = ('recommendations', 'safeBets', 'highRisk')
CANCELLED = {'CANCELLED', 'POSTPONED', 'SUSPENDED', 'AWARDED'}
IN_PLAY = {'IN_PLAY', 'PAUSED', 'LIVE', 'EXTRA_TIME', 'PENALTY_SHOOTOUT'}


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def atomic_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    tmp.replace(path)


def pick_outcome(market: str, home: int, away: int):
    if market == 'H': return home > away
    if market == 'U': return home == away
    if market == 'B': return home < away
    if market == 'O25': return home+away >= 3
    if market == 'U25': return home+away < 3
    if market == 'O35': return home+away >= 4
    if market == 'BTTS': return home > 0 and away > 0
    return None


def score_pick(pick: dict, match: dict) -> dict:
    """Settle only on official FINISHED with integer fullTime goals."""
    out = deepcopy(pick)
    status = match.get('status', '')
    score = match.get('score') or {}
    duration = score.get('duration')
    # Football wagers are normally graded over 90 minutes, not extra time.
    # If regularTime is unavailable after ET/penalties, do not guess.
    settle_score = (score.get('regularTime') if duration in ('EXTRA_TIME','PENALTY_SHOOTOUT')
                    else score.get('fullTime')) or {}
    home, away = settle_score.get('home'), settle_score.get('away')
    display_score = score.get('fullTime') or {}
    result = {'status': 'scheduled'}
    if status in IN_PLAY:
        # Only show a match minute if supplied by the provider.
        minute = match.get('minute')
        if type(minute) is int and 0 < minute <= 130:
            result['minute'] = minute
        if status == 'PAUSED':
            result['phase'] = 'Pause'
        elif status == 'EXTRA_TIME':
            result['phase'] = 'Ekstraomganger'
        elif status == 'PENALTY_SHOOTOUT':
            result['phase'] = 'Straffer'
        else:
            result['phase'] = 'Live'
    if status in CANCELLED:
        result['status'] = 'postponed' if status == 'POSTPONED' else 'void'
    elif status in IN_PLAY:
        result['status'] = 'live'
    elif status == 'FINISHED' and not (type(home) is int and type(away) is int):
        result['status'] = 'unverified'
    elif status == 'FINISHED' and type(home) is int and type(away) is int:
        hit = pick_outcome(str(pick.get('market') or ''), home, away)
        result['status'] = 'won' if hit is True else 'lost' if hit is False else 'unverified'
    if status in (IN_PLAY | {'FINISHED'}):
        dh, da = display_score.get('home'), display_score.get('away')
        if type(dh) is int and type(da) is int:
            result['score'] = {'home': dh, 'away': da}
    out['result'] = result
    return out


def with_initial_results(data: dict):
    snapshot = deepcopy(data)
    for key in CATEGORIES:
        snapshot[key] = [dict(p, result={'status': 'scheduled'}) for p in snapshot.get(key, [])]
    snapshot['editionDate'] = snapshot.get('localDate')
    snapshot['resultUpdatedAt'] = None
    snapshot['editionLocked'] = True
    return snapshot


def apply_results(snapshot: dict, matches: list, at: str | None = None):
    """Update score/status while leaving original recommendations and prices untouched."""
    updated = deepcopy(snapshot)
    lookup = {str(m.get('id')): m for m in matches if m.get('id') is not None}
    if not lookup:
        return updated, False
    changed = False
    for key in CATEGORIES:
        out = []
        for p in updated.get(key, []):
            match = lookup.get(str(p.get('matchId')))
            if match:
                new = score_pick(p, match)
                # A temporary lag in a provider feed must not erase a settled bet.
                if p.get('result', {}).get('status') in ('won', 'lost', 'void') and new.get('result', {}).get('status') in ('scheduled', 'live', 'unverified'):
                    new['result'] = p['result']
                if new.get('result') != p.get('result'):
                    changed = True
                out.append(new)
            else:
                out.append(p)
        updated[key] = out
    if changed:
        updated['resultUpdatedAt'] = at or datetime.now(timezone.utc).isoformat()
    return updated, changed


def fetch_results(snapshot: dict, key: str):
    """Fetch one date-scoped match list; filter locally by the saved match IDs.

    football-data.org documents dateFrom/dateTo for the matches endpoint.
    A bare `ids=...` query is not a documented list filter and must not be
    relied on for result matching. Nothing is fetched from the browser.
    """
    if not key:
        raise RuntimeError('FOOTBALL_DATA_API_KEY is missing')
    ids = {str(p.get('matchId')) for category in CATEGORIES
           for p in snapshot.get(category, []) if str(p.get('matchId', '')).isdigit()}
    if not ids:
        return []
    edition = date.fromisoformat(snapshot.get('editionDate') or snapshot['localDate'])
    url = 'https://api.football-data.org/v4/matches?' + urlencode({
        'dateFrom': (edition - timedelta(days=1)).isoformat(),
        'dateTo': (edition + timedelta(days=2)).isoformat()})
    req = Request(url, headers={'X-Auth-Token': key,
                                'User-Agent': 'OddsGeneratoren/0.9 (personal research)'})
    with urlopen(req, timeout=35) as resp:
        data = json.load(resp)
    rows = data.get('matches')
    if not isinstance(rows, list):
        raise ValueError('Unknown match results response')
    return [m for m in rows if str(m.get('id')) in ids]


def save_active(snapshot: dict):
    atomic_json(STATE, snapshot)
    atomic_json(PUBLIC, snapshot)


def create_edition(new_snapshot: dict, prior: dict | None, api_key: str):
    if new_snapshot.get('dataStatus', {}).get('fixtures') != 'ok':
        raise ValueError('No verified fixture feed; old edition must remain')
    if new_snapshot.get('dataStatus', {}).get('odds') == 'error':
        raise ValueError('Odds provider error; old edition must remain')
    if prior and prior.get('editionDate') == new_snapshot.get('localDate'):
        # Re-running an edition is an explicit replacement, never an automatic status poll.
        pass
    if prior and prior.get('editionDate') != new_snapshot.get('localDate'):
        # Settle overnight outcomes before archiving the old daily edition.
        if api_key:
            try:
                prior, _ = apply_results(prior, fetch_results(prior, api_key))
            except (OSError, ValueError, RuntimeError) as exc:
                print('WARN: previous day result reconciliation failed:', type(exc).__name__)
        old_date = str(prior.get('editionDate') or prior.get('localDate') or '')
        if old_date and old_date.replace('-', '').isdigit():
            atomic_json(HISTORY / f'{old_date}.json', prior)
    return with_initial_results(new_snapshot)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=('daily','results','deploy'))
    args = p.parse_args()
    previous = read_json(STATE)
    if args.mode == 'daily':
        # `scripts/build_data.py` runs BEFORE this command, writes a temporary public JSON.
        data = read_json(PUBLIC)
        if data is None:
            raise SystemExit('Snapshot not generated')
        save_active(create_edition(data, previous, os.getenv('FOOTBALL_DATA_API_KEY','').strip()))
        print('EDITION_CREATED='+str(data.get('localDate')))
    elif args.mode == 'results':
        if not previous:
            print('NO_ACTIVE_EDITION')
            return
        matches = fetch_results(previous, os.getenv('FOOTBALL_DATA_API_KEY','').strip())
        revised, changed = apply_results(previous, matches)
        if changed:
            save_active(revised)
            print('RESULTS_CHANGED=1')
        else:
            # Ensure the public copy is reconstructed even on empty changes.
            atomic_json(PUBLIC, previous)
            print('RESULTS_CHANGED=0')
    else:
        if previous:
            atomic_json(PUBLIC, previous)
        print('DEPLOY_EXISTING_EDITION')


if __name__ == '__main__':
    main()
