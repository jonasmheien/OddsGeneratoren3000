"""Offline integration test: realistic provider-shaped responses (never live odds)."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from build_data import build_snapshot, extract_market_odds, fixed_odds_event, sports_today

class FullPipelineTests(unittest.TestCase):
    def test_end_to_end_provider_shapes(self):
        now=datetime(2026,10,30,8,0,tzinfo=timezone.utc)
        kickoff=now+timedelta(hours=12)
        fixtures=[]
        for i in range(7):
            d=now-timedelta(days=i+1)
            fixtures.append({'id':100+i,'utcDate':d.isoformat(),'status':'FINISHED',
                'homeTeam':{'id':1,'shortName':'Nordby'},'awayTeam':{'id':10+i,'shortName':'Opponent A'},
                'competition':{'code':'PL','name':'Premier League'},'score':{'fullTime':{'home':3,'away':0}}})
            fixtures.append({'id':200+i,'utcDate':d.isoformat(),'status':'FINISHED',
                'homeTeam':{'id':20+i,'shortName':'Opponent B'},'awayTeam':{'id':2,'shortName':'Fjordby'},
                'competition':{'code':'PL','name':'Premier League'},'score':{'fullTime':{'home':2,'away':0}}})
        game={'id':999,'utcDate':kickoff.isoformat(),'status':'SCHEDULED',
              'homeTeam':{'id':1,'shortName':'Nordby'}, 'awayTeam':{'id':2,'shortName':'Fjordby'},
              'competition':{'code':'PL','name':'Premier League'}}
        fixtures.append(game)
        source={'home_team':'Nordby FC','away_team':'Fjordby FC','commence_time':kickoff.isoformat(),
          'bookmakers':[{'title':name, 'last_update':(now-timedelta(minutes=20)).isoformat(),
              'markets':[{'key':'h2h','last_update':(now-timedelta(minutes=20)).isoformat(),
              'outcomes':[{'name':'Nordby FC','price':price},{'name':'Draw','price':4.0},{'name':'Fjordby FC','price':5.0}]}]}
              for name,price in [('Book A',1.80),('Book B',1.86)]]}
        matched=fixed_odds_event({'home':'Nordby','away':'Fjordby','kickoff':kickoff.isoformat()},[source])
        self.assertTrue(matched)
        self.assertIn('H', extract_market_odds(matched, {}, now))
        self.assertEqual(sports_today(fixtures,now),['soccer_epl'])
        result=build_snapshot(now,fixtures,[source],[],[],{'fixtures':'ok','odds':'ok'})
        self.assertEqual(len(result['recommendations']),1)
        self.assertEqual(result['recommendations'][0]['home'],'Nordby')
        self.assertEqual(result['recommendations'][0]['market'],'H')
        self.assertEqual(result['recommendations'][0]['bookmakers'],2)
        self.assertEqual(result['recommendations'][0]['oddsSource'],'The Odds API · bookmaker-median')

if __name__ == '__main__': unittest.main()
