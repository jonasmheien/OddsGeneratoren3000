import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from recommend import analyze_match, curated_picks
from build_data import sports_today

class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,30,10,0,tzinfo=timezone.utc)
        odds={'price':2.50,'books':3,'lastUpdated':(self.now-timedelta(hours=1)).isoformat()}
        self.m={'id':'42','league':'Premier League','home':'Nordby','away':'Fjordby','kickoff':(self.now+timedelta(hours=6)).isoformat(),
                'status':'SCHEDULED','model':{'quality':'basic','sample':[6,6],
                'probabilities':{'H':.52,'B':.23,'O25':.56,'U25':.44,'O35':.29,'BTTS':.50}},
                'odds':{'H':odds},'predictions':[], 'formHome':'WWDWWW','formAway':'LWWLLD'}

    def test_requires_current_odds(self):
        self.assertEqual(analyze_match(self.m,self.now)[0]['market'],'H')
        self.m['odds']['H']['lastUpdated']=(self.now-timedelta(hours=13)).isoformat()
        self.assertEqual(analyze_match(self.m,self.now),[])

    def test_requires_multiple_bookmakers_and_good_form(self):
        self.m['odds']['H']['books']=1
        self.assertEqual(analyze_match(self.m,self.now),[])
        self.m['odds']['H']['books']=3
        self.m['model']['sample']=[6,4]
        self.assertTrue(any(x['category']=='high' for x in analyze_match(self.m,self.now)))

    def test_high_risk_accepts_three_not_two(self):
        self.m['model']['sample']=[3,3]
        self.m['model']['quality']='exploratory'
        result=analyze_match(self.m,self.now)
        self.assertTrue(result)
        self.assertEqual(result[0]['category'],'high')
        self.assertEqual(result[0]['evidenceLevel'],'begrenset')
        self.m['model']['sample']=[3,2]
        self.assertEqual(analyze_match(self.m,self.now),[])

    def test_low_odds_requires_five_matches(self):
        self.m['model']['sample']=[4,4]
        self.m['model']['quality']='exploratory'
        self.m['odds']['H']['price']=1.4
        self.m['model']['probabilities']['H']=.85
        self.assertEqual(analyze_match(self.m,self.now),[])

    def test_cannot_pick_started_or_many_picks_same_match(self):
        self.m['kickoff']=(self.now-timedelta(seconds=1)).isoformat()
        self.assertEqual(analyze_match(self.m,self.now),[])
        self.m['kickoff']=(self.now+timedelta(hours=6)).isoformat()
        results=curated_picks([self.m]*7,self.now,5)
        self.assertLessEqual(len(results),5)
        self.assertEqual({x['matchId'] for x in results},{'42'})

    def test_external_conflict_blocks_candidate(self):
        self.m['predictions']=[{'source':'source A','probabilities':{'H':.25}}]
        self.assertEqual(analyze_match(self.m,self.now),[])

    def test_safe_is_not_the_same_as_low_odds(self):
        self.m['odds']['H']['price']=1.4
        self.m['model']['probabilities']['H']=.60
        self.assertEqual(analyze_match(self.m,self.now),[])
        self.m['model']['probabilities']['H']=.78
        self.assertEqual(analyze_match(self.m,self.now)[0]['category'],'safe')

    def test_dynamic_leagues_today_only(self):
        def f(code,hours, status='SCHEDULED'):
            return {'status':status,'utcDate':(self.now+timedelta(hours=hours)).isoformat(),'competition':{'code':code}}
        sports=sports_today([f('PL',3),f('PL',5),f('SA',5),f('PD',5),f('PL',-3),f('ELC',6)],self.now)
        self.assertEqual(sports[0],'soccer_epl')
        self.assertEqual(len(sports),3)

if __name__=='__main__':unittest.main()
