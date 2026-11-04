from __future__ import annotations
import sys
import unittest
from datetime import date,datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from expanded_sources_v23 import normalize_fixture,discover,available_sports,results_for,odds_remaining


def example(*, fixture_id=11, date='2026-11-05T17:00:00+00:00', status='NS',league='Eliteserien',country='Norway', home=1,away=2, goals=None):
    return {'fixture':{'id':fixture_id,'date':date,'status':{'short':status}},
            'league':{'name':league,'country':country},
            'teams':{'home':{'id':home,'name':'Fredrikstad'},'away':{'id':away,'name':'Viking'}},
            'goals':goals or {'home':None,'away':None}}

class ExpandedSourcesTests(unittest.TestCase):
    def test_strictly_mapped_and_namespaced(self):
        m=normalize_fixture(example())
        self.assertEqual(m['id'],'apf:11')
        self.assertEqual(m['competition']['code'],'APF-NO1')
        self.assertEqual(m['homeTeam']['id'],'apf:1')
        self.assertIsNone(normalize_fixture(example(league='1. Division')))
        self.assertIsNone(normalize_fixture(example(country='Sweden')))
    def test_history_only_real_finished_scores(self):
        m=normalize_fixture(example(status='FT',goals={'home':3,'away':1}))
        self.assertEqual(m['score']['fullTime'],{'home':3,'away':1})
        live=normalize_fixture(example(status='2H',goals={'home':2,'away':0}))
        self.assertEqual(live['score']['fullTime']['home'],2)
        self.assertEqual(live['status'],'IN_PLAY')
    def test_extra_time_has_separate_ninety_minute_score(self):
        row=example(status='AET', goals={'home':2,'away':1})
        row['score']={'fulltime':{'home':1,'away':1}}
        normalized=normalize_fixture(row)
        self.assertEqual(normalized['score']['duration'],'EXTRA_TIME')
        self.assertEqual(normalized['score']['regularTime'],{'home':1,'away':1})
    def test_discovers_and_bounds_team_history_calls(self):
        calls=[]
        def fake(path,params,key):
            calls.append(dict(params))
            if 'date' in params:return [example()]
            return [example(fixture_id=100+params['team'],date='2026-10-01T16:00:00Z',status='FT',goals={'home':2,'away':1})]
        now=datetime(2026,11,5,9,tzinfo=timezone.utc)
        items,notes=discover(date(2026,11,5),now,'key',max_history_calls=1,request=fake)
        self.assertEqual(len(calls),2)
        self.assertEqual(len(items),2)
        self.assertFalse(notes)
        self.assertEqual(available_sports(items,now),['soccer_norway_eliteserien'])
    def test_unavailable_season_keeps_other_sources_working(self):
        def no_data(*args):raise ValueError('missing')
        games,issues=discover(date(2026,11,5),datetime(2026,11,5,tzinfo=timezone.utc),'k',request=no_data)
        self.assertEqual(games,[])
        self.assertTrue(issues)
    def test_results_use_provider_ids(self):
        def fake(path,params,key):
            self.assertEqual(params,{'ids':'11'})
            return [example(status='FT',goals={'home':2,'away':0})]
        rows=results_for(['apf:11','15'], 'key',request=fake)
        self.assertEqual(rows[0]['score']['fullTime']['home'],2)
    def test_quota_header_is_read_without_charging_endpoint(self):
        class Response:
            headers={'x-requests-remaining':'62'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
        self.assertEqual(odds_remaining('test',urlopen_fn=lambda *args,**kwargs: Response()),62)

if __name__=='__main__':unittest.main()
