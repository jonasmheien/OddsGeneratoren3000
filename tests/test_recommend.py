import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from recommend import analyze_match, curated_picks, category_picks
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

    def test_market_favorite_for_three_game_teams(self):
        self.m['model']['sample']=[3,3]
        self.m['model']['quality']='exploratory'
        now=self.now
        mk=lambda price,books=4: {'price':price,'books':books,
              'lastUpdated':(now-timedelta(hours=1)).isoformat()}
        self.m['odds']={'H':mk(1.35),'U':mk(5.2),'B':mk(9.0)}
        result=analyze_match(self.m,self.now)
        fav=[x for x in result if x['category']=='safe']
        self.assertEqual(len(fav),1)
        self.assertEqual(fav[0]['probabilitySource'],'market')
        self.assertIsNone(fav[0]['modelEdge'])
        self.assertGreater(fav[0]['probability'],.65)
        self.assertEqual(len(category_picks([self.m],self.now,'safe')),1)

    def test_market_favorite_does_not_claim_safety_without_form(self):
        now=self.now
        mk=lambda price: {'price':price,'books':4,'lastUpdated':(now-timedelta(hours=1)).isoformat()}
        self.m['odds']={'H':mk(1.35),'U':mk(5.2),'B':mk(9.0)}
        self.m['model']['sample']=[2,2]
        self.assertEqual(analyze_match(self.m,now),[])

    def test_market_favorite_requires_complete_fresh_consensus(self):
        mk=lambda p,books=4: {'price':p,'books':books,
             'lastUpdated':(self.now-timedelta(hours=1)).isoformat()}
        self.m['odds']={'H':mk(1.35),'U':mk(5.2),'B':mk(9.0)}
        self.m['odds']['U']['lastUpdated']=(self.now-timedelta(hours=13)).isoformat()
        self.assertFalse(any(p.get('probabilitySource')=='market' for p in analyze_match(self.m,self.now)))
        self.m['odds']['U']=mk(5.2,1)
        self.assertFalse(any(p.get('probabilitySource')=='market' for p in analyze_match(self.m,self.now)))

    def test_market_favorite_not_automatically_value(self):
        now=self.now
        mk=lambda price: {'price':price,'books':4,'lastUpdated':(now-timedelta(hours=1)).isoformat()}
        self.m['odds']={'H':mk(1.35),'U':mk(5.2),'B':mk(9.0)}
        fav=[p for p in analyze_match(self.m,self.now) if p['probabilitySource']=='market'][0]
        self.assertIsNone(fav['modelEdge'])
        self.assertTrue(fav['probability'] < 1/1.35)

    def test_dynamic_leagues_today_only(self):
        def f(code,hours, status='SCHEDULED'):
            return {'status':status,'utcDate':(self.now+timedelta(hours=hours)).isoformat(),'competition':{'code':code}}
        sports=sports_today([f('PL',3),f('PL',5),f('SA',5),f('PD',5),f('PL',-3),f('ELC',6)],self.now)
        self.assertEqual(sports[0],'soccer_epl')
        self.assertEqual(len(sports),3)

if __name__=='__main__':unittest.main()
