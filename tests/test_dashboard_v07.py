import sys, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import recommend, build_data

class DashboardV07Tests(unittest.TestCase):
    def test_each_category_up_to_five_not_shadowed(self):
        now=datetime(2026,11,3,8,0,tzinfo=timezone.utc)
        matches=[{'id':f'game{i}','league':'CL','home':f'H{i}','away':f'A{i}',
                 'kickoff':(now+timedelta(hours=4)).isoformat()} for i in range(7)]
        def fake(m,now):
            return [dict(market='H',category='safe',score=10,price=1.4),
                    dict(market='B',category='high',score=9,price=3.1)]
        with patch.object(recommend,'analyze_match',side_effect=fake):
            safe=recommend.category_picks(matches,now,'safe',limit=5)
            high=recommend.category_picks(matches,now,'high',limit=5)
        self.assertEqual(len(safe),5)
        self.assertEqual(len(high),5)
        self.assertTrue(all(x['category']=='safe' for x in safe))
        self.assertTrue(all(x['category']=='high' for x in high))

    def test_optional_independent_api_uses_strict_match_and_percent(self):
        now=datetime(2026,11,3,8,0,tzinfo=timezone.utc)
        kickoff=(now+timedelta(hours=12)).isoformat()
        fixtures=[{'id':123,'status':'SCHEDULED','utcDate':kickoff,
            'homeTeam':{'id':1,'name':'Barcelona'}, 'awayTeam':{'id':2,'name':'Aston Villa'}}]
        event={'fixture':{'id':991,'date':kickoff}, 'teams':{'home':{'name':'FC Barcelona'},'away':{'name':'Aston Villa'}}}
        response={'response':[{'predictions':{'percent':{'home':'68%','draw':'21%','away':'11%'}}}]}
        with patch.object(build_data,'fetch_json',side_effect=[{'response':[event]},response]):
            results,errors=build_data.independent_api_predictions(fixtures,now,'test-key')
        self.assertEqual(errors,[])
        self.assertEqual(results['123'][0]['probabilities']['H'],.68)
        self.assertEqual(results['123'][0]['source'],'API-Football Predictions')

    def test_no_fabricated_tips_with_no_matches(self):
        now=datetime(2026,11,3,8,0,tzinfo=timezone.utc)
        snapshot=build_data.build_snapshot(now,[],[],[],[],{'fixtures':'ok','odds':'ok'})
        self.assertEqual(snapshot['recommendations'],[])
        self.assertEqual(snapshot['safeBets'],[])
        self.assertEqual(snapshot['highRisk'],[])
        self.assertEqual(snapshot['coverage']['matchedOdds'],0)
        self.assertTrue(all(x['state']!='connected' for x in snapshot['sources'] if x['name']=='Eksterne prognoser'))

if __name__=='__main__':unittest.main()
