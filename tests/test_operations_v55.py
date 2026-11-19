"""Credit, result-identity and failure-persistence regressions. No live APIs."""
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from odds_budget_v55 import OddsClient, BudgetExceeded, atomic_json
from operations_v55 import classify, record_attempt, publish
from result_sources_v51 import match_saved_picks, selection_key, uefa_competition
from result_cache_v55 import cached_fetch, verified_evidence
from publication_policy_v53 import first_records
from lifecycle import score_pick
from edition_status_v51 import no_supported_prices
import lifecycle
import build_data
import market_scan_v14 as scanner
from build_data import SPORT_BY_COMPETITION
from odds_first_v25 import COMPETITIONS
from test_market_scan_v14 import snapshot as scanner_snapshot
from test_sportmonks_v45 import game

NOW = datetime(2026, 11, 19, 9, tzinfo=timezone.utc)
URL = 'https://api.the-odds-api.com/v4/sports/soccer_brazil_campeonato/odds?apiKey=PRIVATE_TEST&markets=h2h,totals&regions=eu'


class Response(io.BytesIO):
    def __init__(self, rows, remaining=15, charge=2):
        super().__init__(json.dumps(rows).encode())
        self.headers = {'x-requests-remaining': str(remaining), 'x-requests-last': str(charge)}


class CreditBudgetV55(unittest.TestCase):
    def test_daily_limit_persists_between_processes_and_cache_retains_quote_time(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            quote = [{'id': 'real', 'last_update': '2026-11-19T08:59:00Z'}]
            def fetch(*args, **kwargs):
                calls.append(1)
                return Response(quote)
            client = OddsClient(directory, NOW, opener=fetch)
            client.note_remaining(17)
            self.assertEqual(client.get(URL), quote)
            retry = OddsClient(directory, NOW + timedelta(minutes=10), opener=fetch)
            self.assertEqual(retry.allowance('core'), 0)
            self.assertEqual(retry.get(URL.replace('PRIVATE_TEST', 'ROTATED_TEST')), quote)
            self.assertEqual(calls, [1])
            with self.assertRaises(BudgetExceeded):
                retry.get(URL.replace('soccer_brazil_campeonato', 'soccer_epl'))
            for path in Path(directory).rglob('*.json'):
                self.assertNotIn('PRIVATE_TEST', path.read_text())
                self.assertNotIn('ROTATED_TEST', path.read_text())
            self.assertEqual(retry.summary()['dailyCredits']['core'], 2)

    def test_unknown_or_low_quota_blocks_every_optional_paid_request(self):
        with tempfile.TemporaryDirectory() as directory:
            def no_network(*args, **kwargs):
                raise AssertionError('Optional request spent credits')
            client = OddsClient(directory, NOW, opener=no_network)
            for remaining in (None, 0, 17, 127):
                if remaining is not None:
                    client.note_remaining(remaining)
                self.assertEqual(client.allowance('extra'), 0)
                with self.assertRaises(BudgetExceeded):
                    client.get(URL, purpose='extra')

    def test_empty_response_costs_zero_and_catalog_is_free(self):
        with tempfile.TemporaryDirectory() as directory:
            client = OddsClient(directory, NOW, opener=lambda *a, **k: Response([], 17, 0))
            client.note_remaining(17)
            self.assertEqual(client.get(URL), [])
            self.assertEqual(client.allowance('core'), 2)
            self.assertEqual(client.get('https://api.the-odds-api.com/v4/sports/?apiKey=PRIVATE_TEST'), [])
            self.assertEqual(client.summary()['dailyCredits']['core'], 0)

    def test_expired_cache_cannot_bypass_daily_budget_and_new_day_can_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            client = OddsClient(directory, NOW, opener=lambda *a, **k: Response([{'id': 1}]))
            client.note_remaining(17)
            client.get(URL)
            with self.assertRaises(BudgetExceeded):
                OddsClient(directory, NOW + timedelta(hours=2)).get(URL)
            next_day = OddsClient(directory, NOW + timedelta(days=1), opener=lambda *a, **k: Response([{'id': 2}]))
            self.assertEqual(next_day.get(URL), [{'id': 2}])

    def test_invalid_credit_journal_never_authorizes_a_request(self):
        with tempfile.TemporaryDirectory() as directory:
            for broken in ({'schemaVersion': 3}, {}, {'schemaVersion':55,'days':{'2026-11-19':{'core':-10}}}):
                atomic_json(Path(directory) / 'state/api-usage-v55.json', broken)
                with self.assertRaises(ValueError):
                    OddsClient(directory, NOW)

    def test_timeout_reserves_uncertain_cost_and_prevents_repeated_paid_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            def fail(*args, **kwargs):
                raise TimeoutError('PRIVATE_TEST')
            client = OddsClient(directory, NOW, opener=fail)
            client.note_remaining(17)
            with self.assertRaises(TimeoutError):
                client.get(URL)
            retry = OddsClient(directory, NOW + timedelta(minutes=10), opener=fail)
            with self.assertRaises(BudgetExceeded):
                retry.get(URL)
            self.assertEqual(retry.summary()['uncertainCredits'], 2)
            self.assertNotIn('PRIVATE_TEST', (Path(directory) / 'state/api-usage-v55.json').read_text())

    def test_brazil_fixture_and_bookmaker_mapping_are_both_supported(self):
        self.assertEqual(SPORT_BY_COMPETITION['BSA'], 'soccer_brazil_campeonato')
        self.assertIn(SPORT_BY_COMPETITION['BSA'], COMPETITIONS)

    def test_core_enrichment_uses_the_same_persisted_optional_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def fetch(*args, **kwargs):
                calls.append(1)
                return Response({'bookmakers': [{'key': 'book', 'markets': []}]}, 496, 4)
            client = OddsClient(directory, NOW, opener=fetch)
            client.note_remaining(500)
            event = {'id': 'real', 'sport_key': 'soccer_epl', 'commence_time': '2026-11-19T20:00:00Z'}
            with patch.dict(os.environ, {'ODDS_API_KEY': 'PRIVATE_TEST'}), \
                    patch.object(build_data, '_ODDS_CLIENT', client), \
                    patch.object(build_data, 'urlopen', side_effect=AssertionError('Budget bypass')):
                build_data.fetch_extra_event_markets(['soccer_epl'], [event], NOW, max_events=1)
                build_data.fetch_extra_event_markets(['soccer_epl'], [dict(event, id='other')], NOW, max_events=1)
            self.assertEqual(calls, [1])
            self.assertEqual(client.summary()['dailyCredits']['extra'], 4)

    def test_extra_scanner_never_follows_tomorrow_or_unknown_credits(self):
        snap = scanner_snapshot()
        snap['localDate'] = '2026-11-04'
        snap['matches'][0]['kickoff'] = '2026-11-05T20:00:00Z'
        at = datetime(2026, 11, 4, 8, tzinfo=timezone.utc)
        with patch.object(scanner, 'get_json', side_effect=AssertionError('Wrong day')):
            scanner.run(snap, 'KEY', '', at)
        snap['matches'][0]['kickoff'] = '2026-11-04T20:00:00Z'
        snap['dataStatus'] = {}
        with patch.object(scanner, 'get_json', return_value=([], None)) as fetch:
            scanner.run(snap, 'KEY', '', at)
        self.assertTrue(all('/odds?' not in call.args[0] for call in fetch.call_args_list))

    def test_relative_workflow_candidate_uses_the_project_credit_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = Path('state/.candidate.json')
            atomic_json(root / candidate, {'generatedAt': NOW.isoformat(), 'coverage': {'matchedOdds': 1}})
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch.object(build_data, 'ROOT', root), patch.object(build_data, 'OUT', candidate), \
                        patch.object(build_data, 'OddsClient', side_effect=RuntimeError('stop')) as client:
                    with self.assertRaisesRegex(RuntimeError, 'stop'):
                        build_data.main()
                    self.assertEqual(client.call_args.args[0], root)
                with patch.object(scanner, 'ROOT', root), patch.object(sys, 'argv', ['scanner', str(candidate)]), \
                        patch.object(scanner, 'OddsClient', side_effect=RuntimeError('stop')) as client:
                    with self.assertRaisesRegex(RuntimeError, 'stop'):
                        scanner.main()
                    self.assertEqual(client.call_args.args[0], root)
            finally:
                os.chdir(previous)


class ResultReconciliationV55(unittest.TestCase):
    def test_aliases_bridge_senior_teams_without_rewriting_publication_keys(self):
        pick = {'matchId': 'odds:abc', 'home': 'Manchester United', 'away': 'Bayern Munich',
                'kickoff': '2026-11-19T20:00:00Z', 'market': 'H', 'league': 'Champions League'}
        key = selection_key(pick)
        row = {'id': 1, 'homeTeam': {'name': 'Manchester United FC'},
               'awayTeam': {'name': 'FC Bayern München'}, 'utcDate': pick['kickoff'],
               'status': 'FINISHED', 'score': {'fullTime': {'home': 2, 'away': 1}}}
        self.assertEqual(len(match_saved_picks([pick], [row])), 1)
        self.assertEqual(selection_key(pick), key)
        for name in ('Manchester United U19', 'Manchester City', 'Manchester United Women'):
            wrong = dict(row, homeTeam={'name': name})
            self.assertEqual(match_saved_picks([pick], [wrong]), [])

    def test_conference_official_evidence_settles_13_public_games_and_leaves_iceland_unknown(self):
        records = first_records(json.loads((ROOT / 'state/hitrate-v51.json').read_text())['records'])
        evidence = verified_evidence(ROOT)
        # Check every saved fixture on this day, irrespective of its current result.
        picks = [p for p in records if p['editionDate'] == '2026-11-05' and p['home'] not in ('AZ Alkmaar', 'Benfica')]
        matched = match_saved_picks(picks, evidence)
        self.assertEqual(len(matched), 13)
        by_id = {row['id']: row for row in matched}
        self.assertEqual(sum(score_pick(p, by_id[p['matchId']])['result']['status'] == 'won'
                             for p in picks if p['matchId'] in by_id), 8)
        self.assertEqual(uefa_competition({'league': 'UEFA Conference League'}), '2019')
        austria = next(p for p in records if p['home'] == 'Austria' and p['away'] == 'Iceland')
        ireland = {'id': 'uefa:official', 'utcDate': austria['kickoff'], 'status': 'FINISHED',
                   'homeTeam': {'name': 'Austria'}, 'awayTeam': {'name': 'Republic of Ireland'},
                   'score': {'fullTime': {'home': 1, 'away': 0}}}
        self.assertEqual(match_saved_picks([austria], [ireland]), [])

    def test_results_failures_are_visible_in_diagnostics(self):
        pick = {'matchId': 'odds:abc', 'home': 'Denmark', 'away': 'Norway',
                'league': 'UEFA Nations League', 'kickoff': '2026-11-17T19:45:00Z'}
        with patch.object(lifecycle, 'urlopen', side_effect=OSError('SECRET_IN_ERROR')):
            rows = lifecycle.fetch_results({'editionDate': '2026-11-17', 'safeBets': [pick]}, '')
        self.assertEqual(rows, [])
        self.assertEqual(rows.diagnostics[0]['state'], 'unavailable')
        self.assertNotIn('SECRET_IN_ERROR', str(rows.diagnostics))

    def test_sportmonks_also_reconciles_saved_bookmaker_ids(self):
        raw = game(when='2026-11-06T18:00:00Z')
        pick = {'matchId': 'odds:danish', 'home': 'Silkeborg IF', 'away': 'FC Midtjylland',
                'league': 'Superliga', 'kickoff': '2026-11-06T18:00:00Z', 'market': 'H'}
        with patch.dict(os.environ, {'SPORTMONKS_API_TOKEN': 'PRIVATE_TOKEN', 'API_FOOTBALL_KEY': ''}), \
                patch('sportmonks_v45.fetch_page', return_value={'data': [raw], 'pagination': {'has_more': False}}) as fetch:
            rows = lifecycle.fetch_results({'editionDate': '2026-11-06', 'safeBets': [pick]}, '')
        self.assertEqual(len(rows), 1)
        self.assertEqual(score_pick(pick, rows[0])['result']['status'], 'won')
        self.assertTrue(all('PRIVATE_TOKEN' not in call.args[0] for call in fetch.call_args_list))
        self.assertIn('/fixtures/date/2026-11-06?', fetch.call_args.args[0])

    def test_results_cache_does_not_requery_within_10_minutes(self):
        with tempfile.TemporaryDirectory() as directory:
            url = 'https://match.uefa.com/v5/matches?competitionId=2019'
            calls = []
            def fetch():
                calls.append(1)
                return [{'id': 100}]
            cached_fetch(directory, 'UEFA', url, fetch, now=NOW)
            cached_fetch(directory, 'UEFA', url, fetch, now=NOW + timedelta(minutes=5))
            self.assertEqual(calls, [1])
            cached_fetch(directory, 'UEFA', url, fetch, now=NOW + timedelta(minutes=11))
            self.assertEqual(calls, [1, 1])


class HealthStatusV55(unittest.TestCase):
    def snapshot(self):
        return {'localDate': '2026-11-19', 'generatedAt': NOW.isoformat(),
                'dataStatus': {'fixtures': 'ok', 'odds': 'empty', 'requestedLeagues': [],
                               'matchdayDiscovery': {'catalogAvailable': True}},
                'coverage': {'upcomingMatches': 2, 'matchedOdds': 0}}

    def test_empty_coverage_quota_and_provider_error_are_separate(self):
        snap = self.snapshot()
        self.assertEqual(classify(snap, NOW)['reason'], 'coverage_limited')
        snap['dataStatus']['oddsBudgetLimited'] = True
        self.assertEqual(classify(snap, NOW)['reason'], 'quota_limited')
        self.assertTrue(no_supported_prices(snap))
        snap['dataStatus']['odds'] = 'error'
        self.assertEqual(classify(snap, NOW)['reason'], 'source_error')
        self.assertFalse(no_supported_prices(snap))

    def test_successful_but_empty_odds_response_is_expected_not_an_outage(self):
        snap = self.snapshot()
        snap['dataStatus'].update(requestedLeagues=['soccer_brazil_campeonato'], successfulOddsRequests=1)
        self.assertTrue(no_supported_prices(snap))
        self.assertEqual(classify(snap, NOW)['reason'], 'waiting_for_odds')

    def test_empty_day_is_not_affected_by_tomorrow_fixtures(self):
        snap = self.snapshot()
        snap['matches'] = [{'kickoff': '2026-11-20T20:00:00Z', 'odds': {'H': {'price': 2}}}]
        self.assertEqual(classify(snap, NOW)['reason'], 'no_fixtures')

    def test_optional_timeout_does_not_hide_available_core_prices(self):
        snap = self.snapshot()
        snap['dataStatus'].update(odds='ok', oddsBudget={'uncertainCredits': 4})
        snap['coverage']['matchedOdds'] = 2
        snap['safeBets'] = [{'market': 'H'}]
        self.assertEqual(classify(snap, NOW)['reason'], 'ready')

    def test_failed_run_publishes_error_and_preserves_last_good_snapshot(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'GITHUB_RUN_ID': 'current'}):
            root = Path(directory)
            active = {'editionDate': '2026-11-17', 'safeBets': [{'price': 1.6}]}
            atomic_json(root / 'state/active.json', active)
            record_attempt(root, self.snapshot(), NOW)
            out = publish(root, NOW, mode='daily', analysis_failed=True)
            # A failed promotion with a successful acquisition must be an error.
            self.assertEqual(out['reason'], 'analysis_error')
            snap = self.snapshot();snap['dataStatus']['odds'] = 'ok';snap['coverage']['matchedOdds'] = 1
            snap['safeBets'] = [{'price': 1.6}]
            record_attempt(root, snap, NOW)
            out = publish(root, NOW, mode='daily', analysis_failed=True)
            self.assertEqual(out['reason'], 'analysis_error')
            self.assertEqual(json.loads((root / 'state/active.json').read_text()), active)

    def test_results_heartbeat_deploys_hourly_and_failure_is_immediate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record_attempt(root, self.snapshot(), NOW)
            self.assertTrue(publish(root, NOW)['changed'])
            self.assertFalse(publish(root, NOW + timedelta(minutes=5))['changed'])
            self.assertTrue(publish(root, NOW + timedelta(hours=1))['changed'])
            self.assertTrue(publish(root, NOW + timedelta(hours=1, minutes=1), results_failed=True)['changed'])
            self.assertEqual(json.loads((root / 'site/data/operations-v55.json').read_text())['results']['state'], 'unavailable')



if __name__ == '__main__':
    unittest.main()
