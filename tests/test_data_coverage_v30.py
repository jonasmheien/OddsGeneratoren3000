"""Offline verification of additional league parsing and conservative caching."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from form_bridge_v30 import parse_csv, load_cached_history
from form_bridge_v30 import SOURCES

NOW = datetime(2026, 11, 5, 10, 30, tzinfo=timezone.utc)


def data_for(code):
    if code in {'NOR', 'SWE', 'DNK', 'POL', 'AUT', 'FIN', 'SWZ', 'ROU'}:
        return ("Country,League,Season,Date,Time,Home,Away,HG,AG,Res\n"
                "Norway,1,2026,02/11/2026,18:00,Bodo Glimt,Molde,2,1,H\n").encode()
    return ("Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
            "02/11/2026,Galatasaray,Fenerbahce,3,2,H\n").encode()


class TestV30Coverage(unittest.TestCase):
    def test_new_extra_league_schema(self):
        match = parse_csv(data_for('NOR'), 'NOR', NOW)[0]
        self.assertEqual(match['score']['fullTime'], {'home': 2, 'away': 1})
        self.assertEqual(match['homeTeam']['id'], 'fdc:NOR:team:bodo glimt')

    def test_previous_season_schema(self):
        match = parse_csv(data_for('T1'), 'T1', NOW)[0]
        self.assertEqual(match['score']['fullTime'], {'home': 3, 'away': 2})

    def test_missing_scores_and_future_games_are_rejected(self):
        body = ("Date,Home,Away,HG,AG\n02/11/2026,A,B,2,\n"
                "07/11/2026,City,United,1,1\n01/11/2026,Epsilon,Follo,0,0\n")
        result = parse_csv(body.encode(), 'NOR', NOW)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['score']['fullTime'], {'home': 0, 'away': 0})

    def test_wrong_columns_fail_visibly(self):
        with self.assertRaises(ValueError):
            parse_csv(b'Date,Home,Score\n02/11/2026,A,1\n', 'NOR', NOW)

    def test_retries_only_failed_v29_sources_once(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'history.json'
            older = parse_csv(data_for('T1'), 'T1', NOW)
            path.write_text(json.dumps({'lastAttempt': (NOW - timedelta(hours=2)).isoformat(),
                                        'matches': older, 'sourcesOk': 1}), encoding='utf-8')
            attempted = []
            def fake_fetch(url):
                for code in SOURCES:
                    if code + '.csv' in url or '/' + code + '.csv' in url:
                        attempted.append(code)
                        return data_for(code)
                raise ValueError('unknown fixture url')
            rows, diagnostics = load_cached_history(NOW, path, fetch=fake_fetch)
            self.assertNotIn('T1', attempted)
            self.assertGreater(len(rows), len(older))
            self.assertIn('NOR', attempted)
            self.assertEqual(diagnostics['mode'], 'migration')
            self.assertEqual(json.loads(path.read_text())['schemaVersion'], 30)
            def no_requery(url):
                raise AssertionError('Unexpected repeated remote download')
            again, state = load_cached_history(NOW + timedelta(hours=1), path, fetch=no_requery)
            self.assertEqual(state['mode'], 'cached')
            self.assertEqual(len(again), len(rows))

    def test_european_odds_competition_recovery(self):
        from odds_first_v25 import COMPETITIONS
        for sport in ('soccer_epl', 'soccer_italy_serie_a', 'soccer_norway_eliteserien',
                      'soccer_sweden_allsvenskan', 'soccer_denmark_superliga'):
            self.assertIn(sport, COMPETITIONS)


if __name__ == '__main__':
    unittest.main()
