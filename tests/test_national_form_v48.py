import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from build_data import build_snapshot
from national_form_v48 import load_history, parse_results, team_identity
from odds_first_v25 import fixtures_from_quotes
from qualify_v20 import qualify

HEADER = 'date,home_team,away_team,home_score,away_score,tournament,neutral'
DAY = date(2026, 11, 12)
KICKOFF = datetime(2026, 11, 12, 19, 45, tzinfo=timezone.utc)


class NationalFormTests(unittest.TestCase):
    def test_ambiguous_scores_and_same_day_rows_do_not_enter_history(self):
        content = '\n'.join([
            HEADER,
            '2026-10-06,Czech Republic,England,1,2,UEFA Nations League,FALSE',
            '2026-10-06,Czechia,England,1,2,UEFA Nations League,FALSE',
            '2026-10-04,Cyprus,Finland,1,1,Friendly,TRUE',
            '2026-10-04,Cyprus,Finland,2,1,Friendly,TRUE',
            '2026-03-31,Czech Republic,Denmark,2,2,FIFA World Cup qualification,FALSE',
            '2026-07-19,Spain,Argentina,1,0,FIFA World Cup,TRUE',
            '2026-11-12,England,Czech Republic,2,0,UEFA Nations League,FALSE',
        ])
        rows = parse_results(content, date(2025, 5, 1), DAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['homeTeam']['id'], team_identity('Czechia'))
        self.assertEqual(team_identity('Türkiye'), team_identity('Turkey'))
        self.assertNotEqual(team_identity('Northern Ireland'), team_identity('Ireland'))

    def test_download_error_keeps_analysis_available(self):
        def unavailable():
            raise OSError('connection failed')

        rows, status = load_history(KICKOFF, fetch=unavailable)
        self.assertEqual(rows, [])
        self.assertEqual(status, {'state': 'unavailable', 'error': 'OSError'})

    def test_bookmaker_fixture_gets_verified_form_in_daily_and_preview_modes(self):
        rows = [HEADER]
        for age in (7, 28, 58, 88, 118, 148, 235, 305, 375, 420):
            day = DAY - timedelta(days=age)
            rows += [f'{day},Czech Republic,France,2,1,Friendly,TRUE',
                     f'{day},England,Belgium,1,1,Friendly,FALSE']
        for at in (KICKOFF - timedelta(hours=25), KICKOFF - timedelta(hours=10)):
            with self.subTest(at=at):
                bookmakers = [
                    {'key': f'book{i}', 'last_update': at.isoformat(), 'markets': [
                        {'key': 'h2h', 'outcomes': [
                            {'name': 'Czechia', 'price': 2.8}, {'name': 'England', 'price': 2.5},
                            {'name': 'Draw', 'price': 3.1},
                        ]},
                    ]}
                    for i in range(3)
                ]
                event = {'id': 'national01', 'sport_key': 'soccer_uefa_nations_league',
                         'home_team': 'Czechia', 'away_team': 'England',
                         'commence_time': KICKOFF.isoformat(), 'bookmakers': bookmakers}
                fixtures = fixtures_from_quotes([event], at, DAY)
                history, status = load_history(at, fetch=lambda: '\n'.join(rows))
                data = build_snapshot(at, fixtures, [event], [], [],
                                      {'nationalForm': status}, target_date=DAY,
                                      national_history=history)
                match = data['matches'][0]
                self.assertEqual(match['model']['sample'], [10, 10])
                self.assertEqual(match['model']['modelMethod'], 'national_form_v48')
                self.assertLess(match['model']['effectiveSample'][0], 10)
                self.assertEqual(data['coverage']['oddsWithVerifiedForm'], 1)
                self.assertEqual(len(match['formMatchesHome']), 5)
                self.assertTrue(match['formMatchesHome'][0]['neutralVenue'])
                self.assertEqual(match['odds']['B']['books'], 3)
                self.assertNotIn('manglende_kamphistorikk', qualify(data)['qualityAudit']['rejections'])
