"""Shared, persisted credit limits and a short cache for bookmaker requests.

Keys and authenticated URLs never enter the journal or cache. Cached prices
retain their supplier timestamps; caching does not make an old quote fresh.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen


class BudgetExceeded(ValueError):
    pass


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def number(value):
    try:
        result = int(value)
        return result if result >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


class OddsClient:
    def __init__(self, root, now=None, *, preview=False, opener=urlopen):
        self.root = Path(root)
        self.now = now or datetime.now(timezone.utc)
        if self.now.tzinfo is None:
            raise ValueError('Timezone-aware clock required')
        self.preview, self.opener = preview, opener
        self.day = self.now.astimezone(timezone.utc).date().isoformat()
        self.path = self.root / 'state/api-usage-v55.json'
        self.cache = self.root / '.cache/odds-v55'
        saved = read_json(self.path)
        self.journal = {'schemaVersion': 55, 'days': {}} if saved is None else saved
        if (not isinstance(self.journal, dict) or self.journal.get('schemaVersion') != 55
                or not isinstance(self.journal.get('days'), dict)
                or any(not isinstance(day, dict) or any(type(value) is not int or value < 0 for value in day.values())
                       for day in self.journal.get('days', {}).values())):
            raise ValueError('Unknown credit journal; refusing paid requests')
        self.denied = []
        self.cache_hits = 0

    @property
    def remaining(self):
        return number(self.journal.get('remaining'))

    def note_remaining(self, remaining):
        remaining = number(remaining)
        if remaining is not None:
            self.journal.update(remaining=remaining, checkedAt=self.now.isoformat())
            self.save()

    def limits(self):
        remaining = self.remaining
        core = 2 if remaining is None or remaining < 50 else 4 if remaining < 100 else 6
        return {'core': core, 'preview': 2 if remaining is not None and remaining >= 64 else 0,
                'extra': 4 if remaining is not None and remaining >= 256 else
                         2 if remaining is not None and remaining >= 128 else 0}

    def allowance(self, purpose):
        spent = self.journal['days'].get(self.day, {}).get(purpose, 0)
        available = max(0, self.limits()[purpose] - spent)
        return min(available, self.remaining) if self.remaining is not None else available

    def save(self):
        # A bounded operational journal, separate from immutable publication data.
        self.journal['days'] = dict(sorted(self.journal['days'].items())[-35:])
        atomic_json(self.path, self.journal)

    def summary(self):
        return {'remaining': self.remaining, 'checkedAt': self.journal.get('checkedAt'),
                'dailyCredits': self.journal['days'].get(self.day, {}),
                'dailyLimits': self.limits(), 'cacheHits': self.cache_hits,
                'denied': list(self.denied),
                'uncertainCredits': self.journal['days'].get(self.day, {}).get('uncertainCredits', 0)}

    def get(self, url, *, purpose=None):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname != 'api.the-odds-api.com':
            raise ValueError('Not a bookmaker API endpoint')
        query = parse_qs(parsed.query)
        paid = parsed.path.rstrip('/').endswith('/odds')
        purpose = purpose or ('extra' if '/events/' in parsed.path else 'preview' if self.preview else 'core')
        markets = query.get('markets', ['h2h'])[0].split(',')
        regions = query.get('regions', ['eu'])[0].split(',')
        estimated = len(set(markets)) * len(set(regions)) if paid else 0
        safe_query = {k: v for k, v in query.items() if k.casefold() not in ('apikey', 'api_key', 'token')}
        token = hashlib.sha256((parsed.path + '?' + urlencode(safe_query, doseq=True)).encode()).hexdigest()
        cache_path = self.cache / (token + '.json')
        cached = read_json(cache_path)
        if isinstance(cached, dict):
            age = self.now.timestamp() - cached.get('savedAt', 0)
            if 0 <= age < cached.get('ttl', 0):
                self.cache_hits += 1
                return cached['data']
        if paid and self.allowance(purpose) < estimated:
            self.denied.append(purpose)
            raise BudgetExceeded('Daily or provider credit limit reached for ' + purpose)
        request = Request(url, headers={'User-Agent': 'OddsGeneratoren3000/5.5'})
        try:
            with self.opener(request, timeout=28) as response:
                data = json.load(response)
                remaining = number(response.headers.get('x-requests-remaining'))
                actual = number(response.headers.get('x-requests-last'))
        except (OSError, ValueError) as error:
            if isinstance(error, HTTPError) and error.headers:
                self.note_remaining(error.headers.get('x-requests-remaining'))
            if paid:
                # A timeout can arrive after the provider charged the request.
                # Reserve its cost instead of retrying it on every schedule.
                known = number(error.headers.get('x-requests-last')) if isinstance(error, HTTPError) and error.headers else None
                charge = known if known is not None else estimated
                day = self.journal['days'].setdefault(self.day, {})
                day[purpose] = day.get(purpose, 0) + charge
                day['requests'] = day.get('requests', 0) + 1
                if known is None:
                    day['uncertainCredits'] = day.get('uncertainCredits', 0) + charge
                self.save()
            raise
        if remaining is not None:
            self.journal.update(remaining=remaining, checkedAt=self.now.isoformat())
        if paid:
            # Empty bookmaker responses are free. When headers are absent,
            # conservatively reserve the documented market x region cost.
            nonempty = bool(data if isinstance(data, list) else (data or {}).get('bookmakers'))
            charge = actual if actual is not None else estimated if nonempty else 0
            day = self.journal['days'].setdefault(self.day, {})
            day[purpose] = day.get(purpose, 0) + charge
            day['requests'] = day.get('requests', 0) + 1
            self.journal['lastPaidAt'] = self.now.isoformat()
        self.save()
        ttl = (3600 if data else 900) if paid else 21600 if parsed.path.rstrip('/').endswith('/sports') else 600
        atomic_json(cache_path, {'savedAt': self.now.timestamp(), 'ttl': ttl, 'data': data})
        return data
