import sys,unittest,os
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_data import extract_market_odds,model_probabilities,build_snapshot
from market_expansion import first_half_probabilities,corner_probabilities
from recommend import analyze_match,MARKET_LABELS
from lifecycle import pick_outcome,score_pick

class ExpandedMarketsTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,11,4,8,tzinfo=timezone.utc)
  self.at=(self.now-timedelta(minutes=12)).isoformat()
 def raw(self):
  bm=[]
  for k in ('maker1','maker2','maker3'):
   bm.append({'key':k,'last_update':self.at,'markets':[
     {'key':'totals','outcomes':[{'name':'Over','point':1.5,'price':1.42},{'name':'Over','point':2.5,'price':1.91},{'name':'Under','point':2.5,'price':1.93}]},
     {'key':'team_totals','outcomes':[{'name':'Over','description':'Home Athletic','point':1.5,'price':1.80},{'name':'Over','description':'Away Club','point':0.5,'price':1.44},{'name':'Over','point':1.5,'price':1.02}]},
     {'key':'totals_h1','outcomes':[{'name':'Over','point':0.5,'price':1.47},{'name':'Under','point':1.5,'price':1.69}]},
     {'key':'btts','outcomes':[{'name':'Yes','price':1.75}]},
     {'key':'alternate_totals_corners','outcomes':[{'name':'Over','point':8.5,'price':1.91}]}
   ]})
  return {'home_team':'Home Athletic','away_team':'Away Club','bookmakers':bm}
 def test_precisely_parses_goals_team_half_and_corners(self):
  odds=extract_market_odds(self.raw(),{'home':'Home Athletic','away':'Away Club'},self.now)
  self.assertTrue({'O15','O25','U25','THO15','TAO05','H1O05','H1U15','BTTS','CO85'}.issubset(odds))
  self.assertEqual(odds['THO15']['books'],3)
  self.assertEqual(odds['THO15']['price'],1.80)
  self.assertNotIn('TAO15',odds)
  self.assertNotIn('THO05',odds)
 def test_dupe_bookmaker_does_not_count_twice(self):
  data=self.raw();data['bookmakers'].append(data['bookmakers'][0])
  result=extract_market_odds(data,{},self.now)
  self.assertEqual(result['BTTS']['books'],3)
 def test_complementary_goal_markets_have_model_odds_and_settlement(self):
  data=self.raw()
  for book in data['bookmakers']:
   for market in book['markets']:
    if market['key']=='btts':
     market['outcomes'].append({'name':'No','price':2.25})
    if market['key']=='team_totals':
     market['outcomes'].append({'name':'Under','description':'Home Athletic','point':1.5,'price':2.14})
  odds=extract_market_odds(data,{},self.now)
  self.assertEqual(odds['THU15']['price'],2.14)
  self.assertEqual(odds['BTTSN']['books'],3)
  model=model_probabilities([(self.now,2,1,'W')]*6,[(self.now,1,1,'D')]*6)
  p=model['probabilities']
  self.assertAlmostEqual(p['THO15']+p['THU15'],1)
  self.assertAlmostEqual(p['BTTS']+p['BTTSN'],1)
  self.assertTrue(pick_outcome('THU15',1,3))
  self.assertFalse(pick_outcome('BTTSN',1,3))
 def test_goal_probs_from_observed_fulltime_scores(self):
  now=self.now
  model=model_probabilities([(now,2,1,'W')]*6,[(now,1,1,'D')]*6)
  p=model['probabilities']
  self.assertGreater(p['O15'],p['O25']);self.assertGreater(p['THO05'],p['THO15'])
  self.assertAlmostEqual(p['U15']+p['O15'],1,places=3)
 def test_half_models_only_given_real_halftime_results(self):
  before=self.now+timedelta(hours=8)
  fixtures=[]
  for i in range(5):
   fixtures.append({'id':i,'utcDate':(self.now-timedelta(days=i+1)).isoformat(),'status':'FINISHED','homeTeam':{'id':1},'awayTeam':{'id':2},'score':{'fullTime':{'home':2,'away':1},'halfTime':{'home':1,'away':0}}})
  self.assertEqual(first_half_probabilities(fixtures[:4],before,1,2),{})
  p=first_half_probabilities(fixtures,before,1,2)
  self.assertGreater(p['H1O05'],p['H1O15'])
  self.assertAlmostEqual(p['H1O15']+p['H1U15'],1,places=3)
 def test_corners_not_estimated_without_historical_stats(self):
  rows=[{'id':x,'utcDate':(self.now-timedelta(days=x+1)).isoformat(),'status':'FINISHED','homeTeam':{'id':1},'awayTeam':{'id':2},'score':{'fullTime':{'home':2,'away':0}}} for x in range(14)]
  self.assertEqual(corner_probabilities(rows,self.now,1,2),{})
 def test_corners_only_with_eight_verifiable_results(self):
  rows=[{'id':x,'utcDate':(self.now-timedelta(days=x+1)).isoformat(),'status':'FINISHED','homeTeam':{'id':1,'statistics':{'corner_kicks':6}},'awayTeam':{'id':2,'statistics':{'corner_kicks':4}},'score':{'fullTime':{'home':2,'away':0}}} for x in range(8)]
  p=corner_probabilities(rows,self.now,1,2)
  self.assertIn('CO85',p);self.assertLessEqual(p['CO95'],p['CO85'])
 def test_lifecycle_team_and_first_half_settlement(self):
  self.assertTrue(pick_outcome('THO15',2,1))
  self.assertFalse(pick_outcome('TAO05',2,0))
  match={'status':'FINISHED','score':{'duration':'REGULAR','fullTime':{'home':3,'away':0},'halfTime':{'home':0,'away':0}}}
  self.assertEqual(score_pick({'market':'H1O05'},match)['result']['status'],'lost')
  self.assertEqual(score_pick({'market':'THO15'},match)['result']['status'],'won')
  self.assertEqual(score_pick({'market':'CO85'},match)['result']['status'],'unverified')
  match['score']['halfTime']={'home':1,'away':0}
  self.assertEqual(score_pick({'market':'H1O05'},match)['result']['status'],'won')
 def test_high_odds_winner_not_falsely_promoted(self):
  mk=lambda p:{'price':p,'books':4,'lastUpdated':self.at}
  match={'id':'x','kickoff':(self.now+timedelta(hours=9)).isoformat(), 'status':'SCHEDULED',
  'model':{'quality':'basic','sample':[6,6],'probabilities':{'H':.35,'B':.45,'U':.20}},
  'odds':{'H':mk(11.18),'U':mk(5.4),'B':mk(1.25)},'predictions':[]}
  self.assertFalse(any(p['market']=='H' for p in analyze_match(match,self.now)))
 def test_team_total_must_have_real_price(self):
  mk=lambda p:{'price':p,'books':3,'lastUpdated':self.at}
  match={'id':'x','kickoff':(self.now+timedelta(hours=9)).isoformat(),'status':'SCHEDULED',
        'model':{'quality':'basic','sample':[6,6],'probabilities':{'THO15':.72,'H1O05':.8}},
        'odds':{'THO15':mk(1.68)},'predictions':[]}
  self.assertIn('THO15',[p['market'] for p in analyze_match(match,self.now)])
  self.assertNotIn('H1O05',[p['market'] for p in analyze_match(match,self.now)])

if __name__=='__main__':unittest.main()
