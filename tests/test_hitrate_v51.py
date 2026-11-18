"""Publication evidence, honest denominators and independent result matching."""
import json
import io
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import hitrate_v51 as hitrate
from lifecycle import score_pick
from result_sources_v51 import match_saved_picks, normalize_uefa, selection_key
from edition_status_v51 import no_supported_prices
import build_data
import lifecycle
from quality_monitor_v42 import publish as publish_monitor

NOW = datetime(2026, 11, 18, 8, tzinfo=timezone.utc)


def pick(mid='odds:example', market='H'):
    return {'matchId': mid, 'home': 'Denmark', 'away': 'Norway',
            'league': 'UEFA Nations League', 'market': market, 'label': 'Hjemmeseier',
            'kickoff': '2026-11-17T19:45:00Z', 'price': 2.4}


def result(home=2, away=1, status='FINISHED'):
    return {'id': 'uefa:100', 'status': status, 'utcDate': '2026-11-17T19:45:00Z',
            'homeTeam': {'name': 'Denmark'}, 'awayTeam': {'name': 'Norway'},
            'score': {'fullTime': {'home': home, 'away': away}},
            'resultSource': 'UEFA', 'resultSourceUrl': 'https://match.uefa.com/v5/matches'}


class HitrateV51(unittest.TestCase):
    def journal(self, root, revisions):
        path = root / 'state/tip-audit-v34/2026-11-17.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'schemaVersion': 34, 'editionDate': '2026-11-17',
                                    'revisions': revisions}))

    def revision(self, groups, at='2026-11-17T08:00:00Z', revision='first'):
        return {'id': revision, 'recordedAt': at, 'groups': groups}

    def test_refresh_provider_id_and_category_move_count_once_at_original_price(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = pick()
            changed = dict(original, price=3.8, matchId='789')
            self.journal(root, [self.revision({'safe': [original]}),
                                self.revision({'high': [changed]}, '2026-11-17T12:00:00Z', 'second')])
            out = hitrate.sync(root, NOW, fetcher=lambda *_: [result()])
            self.assertEqual(out['overall']['total'], 1)
            self.assertEqual(out['categories']['safe']['wins'], 1)
            self.assertEqual(out['categories']['high']['total'], 0)
            ledger = json.loads((root / 'state/hitrate-v51.json').read_text())
            self.assertEqual(ledger['records'][0]['price'], 2.4)
            self.assertEqual(ledger['records'][0]['sourceIds'], ['odds:example', '789'])
            self.assertFalse(hitrate.sync(root, NOW, fetcher=lambda *_: [])['changed'])

    def test_removed_tip_remains_in_lifetime_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.journal(root, [self.revision({'high': [pick()]})])
            hitrate.sync(root, NOW, fetcher=lambda *_: [result(0, 1)])
            self.journal(root, [])
            out = hitrate.sync(root, NOW, fetcher=lambda *_: [])
            self.assertEqual(out['categories']['high']['losses'], 1)
            self.assertEqual(out['categories']['high']['hitRatePct'], 0.0)

    def test_unknown_pending_and_void_are_excluded_from_percentage(self):
        records = [{'result': {'status': s}} for s in
                   ('won', 'won', 'lost', 'void', 'scheduled', 'unverified', 'postponed')]
        stats = hitrate.count(records)
        self.assertEqual(stats['hitRatePct'], 66.7)
        self.assertEqual(stats['settled'], 3)
        self.assertEqual(stats['pending'], 2)
        self.assertEqual(stats['unverified'], 1)
        self.assertEqual(stats['voids'], 1)
        self.assertIsNone(hitrate.count([{'result': {'status': 'unverified'}}])['hitRatePct'])

    def test_late_capture_and_unpublished_candidates_never_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.journal(root, [self.revision({'safe': [pick()]}, '2026-11-17T20:00:00Z')])
            (root / 'state/.candidate.json').write_text(json.dumps({'safeBets': [pick()]}))
            out = hitrate.sync(root, NOW, offline=True)
            self.assertEqual(out['overall']['total'], 0)

    def test_provider_failure_keeps_unknown_tip_out_of_loss_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.journal(root, [self.revision({'watch': [pick()]})])
            def fail(*_):
                raise OSError('Unavailable')
            out = hitrate.sync(root, NOW, fetcher=fail)
            self.assertEqual(out['categories']['watch']['unverified'], 1)
            self.assertEqual(out['categories']['watch']['losses'], 0)
            self.assertIsNone(out['categories']['watch']['hitRatePct'])

    def test_result_updates_previous_edition_and_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.journal(root, [self.revision({'watch': [pick()]})])
            edition = {'editionDate': '2026-11-17', 'interestingObjects': [pick()],
                       'recommendations': [], 'safeBets': [], 'highRisk': []}
            path = root / 'state/history/2026-11-17.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(edition))
            hitrate.sync(root, NOW, fetcher=lambda *_: [result()])
            updated = json.loads(path.read_text())
            self.assertEqual(updated['interestingObjects'][0]['result']['status'], 'won')
            self.assertEqual(updated['interestingObjects'][0]['result']['source'], 'UEFA')

    def test_corrupt_ledger_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'state/hitrate-v51.json'; path.parent.mkdir()
            path.write_text('{broken')
            with self.assertRaises(ValueError):
                hitrate.sync(root, NOW, offline=True)
            self.assertEqual(path.read_text(), '{broken')

    def test_existing_monitor_uses_same_lifetime_results_as_category_cards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.journal(root, [self.revision({'high': [pick()]})])
            hitrate.sync(root, NOW, fetcher=lambda *_: [result(0, 1)])
            publish_monitor(root, NOW)
            report = json.loads((root / 'site/data/performance-v42.json').read_text())
            self.assertEqual(report['sample']['losses'], 1)
            self.assertEqual(report['sample']['wins'], 0)


class ResultIdentityV51(unittest.TestCase):
    def test_bookmaker_only_result_polling_uses_uefa_without_an_odds_request_or_api_key(self):
        row = {'id': '100', 'status': 'FINISHED', 'competition': {'id': '2014'},
               'homeTeam': {'internationalName': 'Denmark', 'teamTypeDetail': 'NATIONAL_MEN_TEAM_A'},
               'awayTeam': {'internationalName': 'Norway', 'teamTypeDetail': 'NATIONAL_MEN_TEAM_A'},
               'kickOffTime': {'dateTime': '2026-11-17T19:45:00Z'},
               'score': {'regular': {'home': 2, 'away': 1}, 'total': {'home': 2, 'away': 1}}}
        urls = []
        def fetch(request, **kwargs):
            urls.append(request.full_url)
            return io.BytesIO(json.dumps([row]).encode())
        with patch.object(lifecycle, 'urlopen', fetch):
            rows = lifecycle.fetch_results({'editionDate': '2026-11-17', 'safeBets': [pick()]}, '')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'odds:example')
        self.assertTrue(all(url.startswith('https://match.uefa.com/') for url in urls))
        self.assertEqual(score_pick(pick(), rows[0])['result']['status'], 'won')

    def test_uefa_ids_bridge_to_bookmaker_ids_and_preserve_regulation_score(self):
        row = {'id': '100', 'status': 'FINISHED', 'competition': {'id': '2014'},
               'homeTeam': {'internationalName': 'Denmark', 'teamTypeDetail': 'NATIONAL_MEN_TEAM_A'},
               'awayTeam': {'internationalName': 'Norway', 'teamTypeDetail': 'NATIONAL_MEN_TEAM_A'},
               'kickOffTime': {'dateTime': '2026-11-17T19:45:00Z'},
               'score': {'regular': {'home': 1, 'away': 1}, 'total': {'home': 2, 'away': 1}}}
        normalized = normalize_uefa(row, 'https://match.uefa.com/v5/matches')
        matches = match_saved_picks([pick()], [normalized])
        self.assertEqual(matches[0]['id'], 'odds:example')
        self.assertEqual(score_pick(pick(), matches[0])['result']['status'], 'lost')
        del row['score']['regular']
        self.assertEqual(score_pick(pick(), normalize_uefa(row, 'source'))['result']['status'], 'unverified')

    def test_wrong_opponent_date_reversed_teams_or_conflicting_scores_rejected(self):
        for update in ({'awayTeam': {'name': 'Sweden'}}, {'utcDate': '2026-11-16T19:45:00Z'},
                       {'homeTeam': {'name': 'Norway'}, 'awayTeam': {'name': 'Denmark'}}):
            self.assertEqual(match_saved_picks([pick()], [dict(result(), **update)]), [])
        self.assertEqual(match_saved_picks([pick()], [result(2, 1), result(1, 2)]), [])

    def test_ireland_alias_does_not_merge_iceland(self):
        ireland = dict(pick(), home='Republic of Ireland')
        alias = dict(ireland, home='Ireland')
        iceland = dict(ireland, home='Iceland')
        self.assertEqual(selection_key(ireland), selection_key(alias))
        self.assertNotEqual(selection_key(ireland), selection_key(iceland))

    def test_no_odds_deferral_requires_catalog_evidence_not_a_feed_error(self):
        obj = {'dataStatus': {'fixtures': 'ok', 'odds': 'empty', 'requestedLeagues': [],
                             'matchdayDiscovery': {'catalogAvailable': True}},
               'coverage': {'matchedOdds': 0, 'upcomingMatches': 1}}
        self.assertTrue(no_supported_prices(obj))
        for key in ('fixtures', 'odds'):
            bad = deepcopy(obj); bad['dataStatus'][key] = 'error'
            self.assertFalse(no_supported_prices(bad))
        obj['dataStatus']['matchdayDiscovery']['catalogAvailable'] = False
        self.assertFalse(no_supported_prices(obj))

    def test_failed_evening_case_reaches_preview_skip_without_touching_daily_edition(self):
        now = datetime(2026, 11, 17, 22, 56, tzinfo=timezone.utc)
        class Clock(datetime):
            @classmethod
            def now(cls, *_):
                return now
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / 'state/.candidate.json'
            fixture = {'id': 123, 'status': 'SCHEDULED', 'utcDate': '2026-11-18T22:00:00Z',
                       'competition': {'code': 'BSA', 'name': 'Brasileirao'},
                       'homeTeam': {'id': 1, 'name': 'Team A'}, 'awayTeam': {'id': 2, 'name': 'Team B'},
                       'score': {'fullTime': {'home': None, 'away': None}}}
            discovery = {'catalogAvailable': True, 'matchesBySport': {}, 'selected': [], 'errors': []}
            with (patch.dict(os.environ, {'ODDS_API_KEY': 'test', 'FOOTBALL_DATA_API_KEY': 'test',
                                          'ODDS_TARGET_DAY_OFFSET': '1'}, clear=True),
                  patch.object(build_data, 'ROOT', root), patch.object(build_data, 'OUT', candidate),
                  patch.object(build_data, 'missing_form_teams', return_value=[]),
                  patch.object(build_data, 'fetch_json', return_value={'matches': [fixture]}),
                  patch.object(build_data, 'discover_matchday_sports', return_value=([], discovery)),
                  patch.object(build_data, 'discover_sportmonks', return_value=([], {'state': 'ok'})),
                  patch.object(build_data, 'odds_remaining', return_value=23),
                  patch.object(build_data, 'datetime', Clock)):
                build_data.main()  # The production failure previously raised SystemExit(1).
            self.assertTrue(no_supported_prices(json.loads(candidate.read_text())))
            command = ('import sys; from datetime import datetime, timezone; '
                       'from unittest.mock import patch; import tomorrow_v24 as t; '
                       'clock=type("Clock",(),{"now":staticmethod(lambda *_:datetime(2026,11,17,22,56,tzinfo=timezone.utc))}); '
                       'sys.argv=["tomorrow_v24.py",sys.argv[1]]; '
                       't.datetime=clock; t.main()')
            out = subprocess.check_output([sys.executable, '-c', command, str(candidate)],
                                          env=dict(os.environ, PYTHONPATH=str(ROOT / 'scripts')), text=True)
            self.assertIn('TOMORROW_PREVIEW_SKIPPED=', out)
            self.assertFalse(candidate.exists())
            self.assertFalse((root / 'site/data/today.json').exists())

    def test_daily_no_odds_deferral_preserves_tips_and_keeps_morning_retry_due(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); candidate = root / 'state/.candidate.json'
            candidate.parent.mkdir()
            today = datetime.now(build_data.OSLO).date().isoformat()
            obj = {'localDate': today, 'waitingForOddsV51': True,
                   'dataStatus': {'fixtures': 'ok', 'odds': 'empty', 'requestedLeagues': [],
                                  'matchdayDiscovery': {'catalogAvailable': True}},
                   'coverage': {'matchedOdds': 0}}
            candidate.write_text(json.dumps(obj))
            active = root / 'state/active.json'; active.write_text(json.dumps({'editionDate': '2026-11-17'}))
            before = active.read_bytes()
            with (patch.object(lifecycle, 'ROOT', root), patch.object(lifecycle, 'STATE', active),
                  patch.object(lifecycle, 'PUBLIC', root / 'site/data/today.json'),
                  patch.object(lifecycle, 'CANDIDATE', candidate), patch.object(sys, 'argv', ['lifecycle.py', 'daily'])):
                lifecycle.main()
            self.assertEqual(active.read_bytes(), before)
            self.assertEqual(json.loads((root / 'site/data/update-status-v51.json').read_text())['state'], 'waiting_for_odds')
            self.assertFalse(candidate.exists())


if __name__ == '__main__':
    unittest.main()
