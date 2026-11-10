"""Regression tests for quota-safe bookmaker league discovery."""
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from matchday_sports_v44 import discover_matchday_sports

NOW = datetime(2026, 11, 9, 18, tzinfo=timezone.utc)
DAY = date(2026, 11, 10)
NL = 'soccer_uefa_nations_league'
DK = 'soccer_denmark_superliga'
EL = 'soccer_uefa_europa_league'
PL = 'soccer_epl'


def fixture(event_id, when='2026-11-10T19:00:00Z'):
    return {'id': event_id, 'commence_time': when,
            'home_team': 'Alpha', 'away_team': 'Beta'}

class MatchdaySportsV44(unittest.TestCase):
    def setUp(self):
        self.events = {}
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        path = urlparse(url).path
        if path.endswith('/sports/'):
            return [{'key': key, 'active': True} for key in (NL, DK, EL, PL)]
        for sport in (NL, DK, EL, PL):
            if path.endswith('/' + sport + '/events'):
                return self.events.get(sport, [])
        raise AssertionError(url)

    def choose(self, known=None, max_sports=3):
        return discover_matchday_sports('TEST_KEY', DAY, NOW, self.fetch,
            'https://api.the-odds-api.com/v4', known, max_sports=max_sports)

    def test_no_paid_requests_for_out_of_date_leagues(self):
        self.events = {EL: [fixture('oldmatch001', '2026-11-12T20:00:00Z')]}
        selected, detail = self.choose([EL])
        self.assertEqual(selected, [])
        self.assertEqual(detail['matchesBySport'], {})
        self.assertNotIn('TEST_KEY', str(detail))

    def test_prioritize_real_nations_and_verified_leagues(self):
        self.events = {NL: [fixture('nations00001')], DK: [fixture('denmark00001')],
                       EL: [fixture('europa00001')], PL: [fixture('premier00001')]}
        selected, _ = self.choose([DK, PL])
        self.assertEqual(selected, [NL, DK, PL])
        self.assertTrue(all('/events?' in u or '/sports/?' in u for u in self.calls))

    def test_catalog_failure_safe_fallback(self):
        def failed(url):
            raise OSError('private_TEST_KEY')
        selected, detail = discover_matchday_sports('TEST_KEY', DAY, NOW,
            failed, 'https://api.the-odds-api.com/v4', [DK])
        self.assertEqual(selected, [DK])
        self.assertNotIn('private_TEST_KEY', str(detail))

    def test_no_fixtures_stays_empty(self):
        selected, detail = self.choose()
        self.assertEqual(selected, [])
        self.assertEqual(detail['selected'], [])

if __name__ == '__main__':
    unittest.main()
