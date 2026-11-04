"""No-network checks of the opponent-adjusted v2.1 form model."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from form_v21 import adjusted_form, effective_form_sample, opponent_indices
from build_data import recent_team_form, build_snapshot
from quality_v20 import screen, rejection_reason

NOW=datetime(2026,11,4,15,0,tzinfo=timezone.utc)

def match(i, day, home, away, hg, ag, status='FINISHED'):
    return {'id':i, 'status':status, 'utcDate':(NOW-timedelta(days=day)).isoformat(),
            'homeTeam':{'id':home},'awayTeam':{'id':away},
            'score':{'fullTime':{'home':hg,'away':ag}}, 'competition':{'code':'PL'}}

class FormV21Tests(unittest.TestCase):
    def test_future_results_never_used_for_indices_or_form(self):
        rows=[match(i,i,1,2,1,1) for i in range(1,6)]+[match(12,-1,1,2,9,0)]
        ratings=opponent_indices(rows,NOW)
        self.assertEqual(ratings[1]['matches'],5)
        self.assertEqual(len(recent_team_form(rows,NOW,1)),5)

    def test_opponent_strength_is_regularized(self):
        games=[match(i,i,12,13,3,0) for i in range(1,10)]
        ratings=opponent_indices(games,NOW)
        self.assertGreater(ratings[12]['attack'],1)
        self.assertGreater(ratings[13]['defence'],1)
        self.assertLessEqual(ratings[12]['attack'],1.35)
        form=[(NOW-timedelta(days=1),2,1,'W',13)]
        self.assertLess(adjusted_form(form,ratings,NOW)[0][1],2)
        self.assertEqual(adjusted_form(form,{},NOW)[0][1],2)

    def test_sixteen_match_lookback_and_age_discount(self):
        games=[match(i,i+1,1,2,1,1) for i in range(30)]
        form=recent_team_form(games,NOW,1)
        self.assertEqual(len(form),16)
        self.assertLess(effective_form_sample(form,NOW),len(form))
        old=[(NOW-timedelta(days=150),1,0,'W') for i in range(8)]
        self.assertLess(effective_form_sample(old,NOW),5)

    def test_effective_sample_blocks_stale_history(self):
        quote={'price':2.2,'books':3,'lastUpdated':(NOW-timedelta(hours=1)).isoformat()}
        m={'id':'77','kickoff':(NOW+timedelta(hours=6)).isoformat(),'status':'SCHEDULED',
           'model':{'sample':[16,16],'effectiveSample':[4.1,4.8], 'quality':'basic',
                    'probabilities':{'H':.62}}, 'odds':{'H':quote}}
        self.assertIsNone(screen(m,'H',NOW))
        self.assertEqual(rejection_reason(m,'H',NOW),'for_lite_historikk')

    def test_abnormal_model_market_gap_not_showcased(self):
        from qualify_v20 import qualify
        m={'id':'77','home':'Home','away':'Away','league':'Test',
           'kickoff':(NOW+timedelta(hours=6)).isoformat(),'status':'SCHEDULED',
           'model':{'sample':[6,6],'quality':'basic','probabilities':{'H':.9}},
           'odds':{'H':{'price':6.0,'books':4,'lastUpdated':NOW.isoformat()}}}
        snap=qualify({'generatedAt':NOW.isoformat(),'matches':[m]})
        self.assertEqual(snap['recommendations'],[])
        self.assertEqual(snap['observations'],[])
        self.assertEqual(snap['qualityAudit']['rejections']['stort_modell_marked_avvik'],1)

if __name__=='__main__':unittest.main()
