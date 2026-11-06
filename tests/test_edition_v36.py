"""v36 date matching: daily snapshot may hold tomorrow matches, picks may not."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from qualify_v20 import qualify

class DateBoundV36(unittest.TestCase):
    def test_no_next_day_recommendation_or_observation(self):
        now='2026-11-06T10:00:00Z'
        def q(price):return {'price':price,'books':15,'lastUpdated':now}
        def match(day):
            return {'id':day,'home':'Home','away':'Away','kickoff':day+'T20:00:00Z',
                'status':'SCHEDULED','odds':{'H':q(2.1),'U':q(3.4),'B':q(3.5)},
                'model':{'probabilities':{'H':.65},'sample':[10,10],
                        'effectiveSample':[9,9],'quality':'basic'}, 'predictions':[]}
        snap={'generatedAt':now,'localDate':'2026-11-06','matches':[match('2026-11-06'),match('2026-11-07')],
              'recommendations':[],'safeBets':[],'highRisk':[],'coverage':{},'dataStatus':{}}
        result=qualify(snap)
        self.assertLessEqual(len(result['recommendations']),1,'One qualified pick maximum per fixture')
        for group in ('recommendations','observations','safeBets','highRisk','interestingObjects'):
            self.assertTrue(all(p['kickoff'][:10]=='2026-11-06' for p in result[group]))
        self.assertEqual(result['modelVersion'],'2.0-foundation')

    def test_preview_uses_its_own_target_date(self):
        now='2026-11-06T10:00:00Z'
        snap={'generatedAt':now,'localDate':'2026-11-07','matches':[{'id':'t','home':'A','away':'B',
           'kickoff':'2026-11-06T21:00:00Z','status':'SCHEDULED','odds':{}}],
           'recommendations':[],'safeBets':[],'highRisk':[],'coverage':{},'dataStatus':{}}
        self.assertEqual(qualify(snap)['recommendations'],[])

if __name__=='__main__': unittest.main()
