"""Offline, no-secret regression tests for Sportmonks v3 free-plan adapter."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlsplit
from sportmonks_v45 import normalize, discover, results_for

NOW = datetime(2026, 11, 10, 10, tzinfo=timezone.utc)


def game(*, fixture_id=123456, league=271, state=5,
         when='2026-11-08T15:00:00Z', scores=True):
    raw = {
        'id': fixture_id, 'league_id': league, 'state_id': state,
        'starting_at': when,
        'participants': [
            {'id': 35, 'name': 'Silkeborg IF', 'meta': {'location': 'home'}},
            {'id': 72, 'name': 'FC Midtjylland', 'meta': {'location': 'away'}},
        ],
        'scores': [],
    }
    if scores:
        for desc in ('CURRENT', '2ND_HALF'):
            for side, number in [('home', 2), ('away', 1)]:
                raw['scores'].append({'description': desc, 'score': {'participant': side, 'goals': number}})
    return raw


class TestSportmonksV45(unittest.TestCase):
    def test_finished_result_is_verified(self):
        r = normalize(game(), NOW)
        self.assertEqual(r['status'], 'FINISHED')
        self.assertEqual(r['score']['fullTime'], {'home': 2, 'away': 1})
        self.assertEqual(r['homeTeam']['id'], 'sm:35')
        self.assertEqual(r['formSource'], 'Sportmonks')
        self.assertEqual(r['competition']['code'], 'SM-DK1')

    def test_scheduled_fixture_has_no_fabricated_goals(self):
        r = normalize(game(state=1, when='2026-11-10T19:00:00Z', scores=False), NOW)
        self.assertEqual(r['status'], 'SCHEDULED')
        self.assertEqual(r['score']['fullTime'], {'home': None, 'away': None})

    def test_scotland_and_playoffs_map_to_correct_league(self):
        for league, code in [(501, 'SM-SC1'), (513, 'SM-SC1'),
                             (271, 'SM-DK1'), (1659, 'SM-DK1')]:
            self.assertEqual(normalize(game(league=league), NOW)['competition']['code'], code)

    def test_reject_unknown_competition_and_missing_or_bogus_scores(self):
        self.assertIsNone(normalize(game(league=8), NOW))
        self.assertIsNone(normalize(game(scores=False), NOW))
        malformed = game()
        malformed['scores'][0]['score']['goals'] = -1
        malformed['scores'][2]['score']['goals'] = -1
        self.assertIsNone(normalize(malformed, NOW))

    def test_no_extra_time_score_used_for_regular_time(self):
        event = game(state=7)
        event['scores'] = [x for x in event['scores'] if x['description'] == 'CURRENT']
        self.assertIsNone(normalize(event, NOW))
        self.assertEqual(normalize(game(state=7), NOW)['score']['fullTime']['home'], 2)

    def test_paginated_verified_history_and_future(self):
        pages = []
        def fetch(url, token):
            self.assertEqual(token, 'PRIVATE_TEST_TOKEN')
            self.assertNotIn(token, url)
            self.assertIn('participants%3Bscores', url)
            page = int(parse_qs(urlsplit(url).query)['page'][0])
            pages.append(page)
            if page == 1:
                return {'data': [game()], 'pagination': {'has_more': True}}
            return {'data': [game(fixture_id=987654, state=1,
                                 when='2026-11-10T19:00:00Z', scores=False)],
                    'pagination': {'has_more': False}}
        rows, info = discover(date(2026, 11, 10), NOW, 'PRIVATE_TEST_TOKEN', request=fetch)
        self.assertEqual(pages, [1, 2])
        self.assertEqual(info['state'], 'ok')
        self.assertEqual(info['finished'], 1)
        self.assertEqual(info['upcoming'], 1)
        self.assertEqual(len(rows), 2)

    def test_failed_page_never_publishes_partial_history_or_secrets(self):
        def fetch(url, token):
            if 'page=1' in url:
                return {'data': [game()], 'pagination': {'has_more': True}}
            raise RuntimeError('PRIVATE_TEST_TOKEN')
        rows, info = discover(date(2026, 11, 10), NOW, 'PRIVATE_TEST_TOKEN', request=fetch)
        self.assertEqual(rows, [])
        self.assertEqual(info['state'], 'unavailable')
        self.assertNotIn('PRIVATE_TEST_TOKEN', str(info))

    def test_results_for_saved_matches_and_exact_ids(self):
        calls = []
        def fetch(url, token):
            self.assertNotIn('PRIVATE_TEST_TOKEN', url)
            self.assertIn('fixtures/multi/123456', url)
            calls.append(url)
            return {'data': [game()]}
        rows = results_for(['sm-match:123456', 'sm-match:123456',
                            'sm-match:bad', 'apf:42'], 'PRIVATE_TEST_TOKEN', request=fetch)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'sm-match:123456')

    def test_all_others_safe_without_key(self):
        self.assertEqual(discover(date(2026, 11, 10), NOW, '')[1]['state'], 'not_configured')

if __name__ == '__main__':
    unittest.main()
