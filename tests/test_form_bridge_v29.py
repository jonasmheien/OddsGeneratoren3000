"""Only known real historical scores and unambiguous names become form."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from form_bridge_v29 import parse_csv, load_cached_history, attach_additional_form

NOW = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


class ExtraFormV29Tests(unittest.TestCase):
    def sample(self, name='Fenerbahce', opponent='Besiktas'):
        rows = ['Date,HomeTeam,AwayTeam,FTHG,FTAG']
        for i in range(7):
            d = (NOW - timedelta(days=10+i*7)).strftime('%d/%m/%Y')
            rows.append(f'{d},{name},{opponent},2,1')
        return ('\n'.join(rows)+'\n').encode()

    def test_csv_includes_verified_finished_scores(self):
        rows = parse_csv(self.sample(), 'T1', NOW)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[0]['score']['fullTime'], {'home':2,'away':1})
        self.assertEqual(rows[0]['homeTeam']['id'], 'fdc:T1:team:fenerbahce')

    def test_future_and_unscored_games_excluded(self):
        raw = b'Date,HomeTeam,AwayTeam,FTHG,FTAG\n07/11/2026,Fenerbahce,Besiktas,2,1\n24/10/2026,Fenerbahce,Besiktas,,\n21/10/2026,Fenerbahce,Besiktas,1,2\n'
        rows = parse_csv(raw, 'T1', NOW)
        self.assertEqual(len(rows),1)

    def test_existing_official_team_id_not_overwritten(self):
        history = parse_csv(self.sample(), 'T1', NOW)
        fixtures = [{'id':'odds:abc', 'homeTeam': {'id':123, 'name':'Fenerbahce'},
                     'awayTeam': {'id':'odds-away:abc', 'name':'Besiktas JK'},
                     'utcDate': '2026-11-05T19:00:00Z', 'status':'SCHEDULED'}]
        def score(a,b):return 1.0 if a==b else 0.0
        combined, info = attach_additional_form(fixtures, history, score)
        self.assertEqual(fixtures[0]['homeTeam']['id'],123)
        self.assertEqual(fixtures[0]['awayTeam']['id'],'fdc:T1:team:besiktas')
        self.assertEqual(info['teamsLinked'],1)
        self.assertEqual(len(combined), 8)

    def test_cache_reused_for_four_days(self):
        count=[]
        def fetch(url):count.append(url); return self.sample()
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'form.json'
            first, stats=load_cached_history(NOW,p,fetch=fetch)
            calls=len(count)
            self.assertEqual(calls,8)
            second, stats=load_cached_history(NOW+timedelta(hours=1),p,fetch=fetch)
            self.assertEqual(calls,len(count))
            self.assertEqual(stats['mode'],'cached')
            self.assertEqual(len(first),len(second))

    def test_failed_fetch_not_retried_in_less_than_four_days(self):
        attempted=[]
        def fetch(url):attempted.append(url); raise OSError('offline')
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'form.json'
            first, stats=load_cached_history(NOW,p,fetch=fetch)
            self.assertEqual(len(attempted),8)
            second,stats=load_cached_history(NOW+timedelta(minutes=5),p,fetch=fetch)
            self.assertEqual(len(attempted),8)
            self.assertEqual(second,[])

if __name__ == '__main__':
    unittest.main()
