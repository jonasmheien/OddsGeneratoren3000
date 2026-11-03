import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
sys.path.insert(0,str(Path(__file__).resolve().parent.parent / 'scripts'))
from build_data import name_score, model_probabilities, fixed_odds_event, extract_market_odds, build_snapshot, predictions_for

class OddsLabTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,30,8,0,tzinfo=timezone.utc)
        self.today=self.now.isoformat()
        self.k=(self.now+timedelta(hours=12)).isoformat()
        self.fixture={'id':42,'status':'SCHEDULED','utcDate':self.k,
            'homeTeam':{'id':1,'shortName':'Liverpool'},'awayTeam':{'id':2,'shortName':'Chelsea'},
            'competition':{'code':'PL','name':'Premier League'}}

    def test_normalize(self):
        self.assertGreater(name_score('Liverpool FC','Liverpool'),.95)
        self.assertGreater(name_score('FC København','Kobenhavn'),.75)
        self.assertLess(name_score('Real Madrid','Real Sociedad'),.75)

    def test_poisson(self):
        values=[(self.now,2,1,'W')]*6
        a=[(self.now,1,2,'L')]*6
        model=model_probabilities(values,a)
        p=model['probabilities']
        self.assertAlmostEqual(p['H']+p['U']+p['B'],1,places=3)
        self.assertAlmostEqual(p['O25']+p['U25'],1,places=3)
        self.assertGreater(p['O25'],p['O35'])
        self.assertIsNone(model_probabilities(values[:2],a))

    def test_odds_not_cross_matched(self):
        m={'home':'Liverpool','away':'Chelsea','kickoff':self.k}
        events=[{'commence_time':self.k,'home_team':'Liverpool FC','away_team':'Chelsea FC', 'bookmakers':[]},
                {'commence_time':self.k,'home_team':'Chelsea','away_team':'Liverpool','bookmakers':[]}]
        self.assertEqual(fixed_odds_event(m,events)['home_team'],'Liverpool FC')
        self.assertEqual(fixed_odds_event(m,[events[1]]),{})

    def test_extract_markets(self):
        odds={'home_team':'Liverpool','away_team':'Chelsea','bookmakers':[
            {'title':'Book A','markets':[{'key':'h2h','outcomes':[{'name':'Liverpool','price':2.1},{'name':'Draw','price':3.2},{'name':'Chelsea','price':3.5}]},
            {'key':'totals','outcomes':[{'name':'Over','price':1.8,'point':2.5},{'name':'Under','price':2.0,'point':2.5}]}]},
            {'title':'Book B','markets':[{'key':'h2h','outcomes':[{'name':'Liverpool','price':2.3}]}]}]}
        result=extract_market_odds(odds, {'home':'Liverpool','away':'Chelsea'})
        self.assertEqual(result['H']['price'],2.2)
        self.assertEqual(result['U']['price'],3.2)
        self.assertEqual(result['O25']['price'],1.8)

    def test_real_fixture_has_no_generated_prob_when_no_history(self):
        result=build_snapshot(self.now,[self.fixture],None,[],[],{'fixtures':'ok','odds':'not_configured'})
        self.assertEqual(len(result['matches']),1)
        self.assertIsNone(result['matches'][0]['model'])
        self.assertEqual(result['matches'][0]['odds'],{})

    def test_manual_prediction_needs_explicit_percentages(self):
        m={'home':'Liverpool','away':'Chelsea','kickoff':self.k}
        date=self.now.date().isoformat()
        preds=predictions_for(m,[{'date':date,'home':'Liverpool','away':'Chelsea','source':'Test source','H':'51','O25':'70','url':'https://example.com'}])
        self.assertEqual(preds[0]['probabilities']['H'],.51)
        self.assertNotIn('U',preds[0]['probabilities'])

if __name__=='__main__':
    unittest.main()
