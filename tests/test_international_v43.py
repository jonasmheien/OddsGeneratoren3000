"""Network-free regression checks for real national-team odds discovery v43."""
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from international_v43 import (INTERNATIONAL_KEYS, available_on_day,
                               discover_international, prioritize_sports)
from odds_first_v25 import COMPETITIONS, fixtures_from_quotes

NOW = datetime(2026, 11, 12, 8, 15, tzinfo=timezone.utc)
DAY = date(2026, 11, 12)
NL = 'soccer_uefa_nations_league'
WCQ = 'soccer_fifa_world_cup_qualifiers_europe'


def event(id='nationsfixture01', home='England', away='Croatia',
          at='2026-11-12T19:45:00Z'):
    return {'id': id, 'commence_time': at, 'home_team': home, 'away_team': away,
            'sport_key': NL,
            'bookmakers': [{'markets': [{'key': 'h2h', 'outcomes': [
                {'name': home, 'price': 1.8}, {'name': away, 'price': 4.2}]}]}]}


class InternationalV43Tests(unittest.TestCase):
    def test_known_provider_keys_registered_as_bookmaker_only_fixtures(self):
        for key in INTERNATIONAL_KEYS:
            self.assertIn(key, COMPETITIONS)
        self.assertEqual(COMPETITIONS[NL][0], 'ODDS-UNL')

    def test_correct_oslo_day_timezone_and_only_future_matches(self):
        ev = [event(), event('other12345', at='2026-11-11T23:30:00Z'),
              event('late00001', at='2026-11-13T00:30:00Z'),
              event('gone00001', at='2026-11-12T07:00:00Z')]
        self.assertEqual(available_on_day(ev, DAY, NOW), 1)
        earlier = datetime(2026, 11, 11, 20, 0, tzinfo=timezone.utc)
        self.assertEqual(available_on_day(ev[:2], DAY, earlier), 2)
        self.assertEqual(available_on_day([event(id='sameevent01'), event(id='sameevent01')], DAY, NOW), 1)

    def test_real_nations_fixture_has_no_fabricated_model_or_score(self):
        items = fixtures_from_quotes([event()], NOW, DAY)
        self.assertEqual(len(items), 1)
        fixture = items[0]
        self.assertEqual(fixture['competition']['code'], 'ODDS-UNL')
        self.assertEqual(fixture['competition']['name'], 'UEFA Nations League')
        self.assertIsNone(fixture['score']['fullTime']['home'])
        self.assertNotIn('model', fixture)
        self.assertIsNone(fixture['formSource'])

    def test_discovery_only_uses_catalogued_active_sports_and_real_events(self):
        urls = []
        def fetch(url):
            urls.append(url)
            path = urlparse(url).path
            if path.endswith('/sports/'):
                return [{'key': NL, 'active': True}, {'key': WCQ, 'active': True},
                        {'key': 'soccer_uefa_euro_qualification', 'active': False}]
            if path.endswith('/'+NL+'/events'):
                return [event(), event('nations00002', 'Italy', 'France')]
            if path.endswith('/'+WCQ+'/events'):
                return [event('qualifier001', 'Germany', 'Netherlands', '2026-11-15T19:45:00Z')]
            raise AssertionError('Unexpected URL: '+path)
        got, details = discover_international('secret', DAY, NOW, fetch,
            'https://api.the-odds-api.com/v4', max_sports=2)
        self.assertEqual(got, [NL])
        self.assertEqual(details['fixturesByCompetition'], {NL: 2})
        self.assertEqual(len(urls), 3)
        self.assertNotIn('secret', str(details))

    def test_no_international_events_falls_back_without_spending_odds(self):
        def fetch(url):
            return [{'key': NL, 'active': True}] if '/sports/?' in url else []
        got, d = discover_international('private', DAY, NOW, fetch,
            'https://api.the-odds-api.com/v4')
        self.assertEqual(got, [])
        self.assertEqual(d['selected'], [])
        self.assertEqual(prioritize_sports(['soccer_epl'], got, 4), ['soccer_epl'])

    def test_catalog_fail_closed_does_not_break_regular_leagues(self):
        def bad(url):
            raise OSError('private-key-leak-in-exception')
        got, details = discover_international('abc', DAY, NOW, bad,
            'https://api.the-odds-api.com/v4')
        self.assertEqual(got, [])
        self.assertNotIn('private-key-leak', str(details))

    def test_priority_keeps_at_least_domestic_slots_when_possible(self):
        self.assertEqual(prioritize_sports(['soccer_epl', 'soccer_efl_champ'],
            [NL], 2), [NL, 'soccer_epl'])
        self.assertEqual(prioritize_sports(['soccer_epl', NL], [NL], 3),
            [NL, 'soccer_epl'])

    def test_invalid_data_rejected(self):
        self.assertEqual(available_on_day([{}, event('id3', home='Norway', away='Norway'),
                          event('bad fixture', home='')], DAY, NOW), 0)


if __name__ == '__main__':
    unittest.main()
