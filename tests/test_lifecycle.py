import unittest, sys, json
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import lifecycle

class LifecycleTests(unittest.TestCase):
    def base(self, market='H', name='safe'):
        item={'matchId':'1234', 'home':'Team A', 'away':'Team B', 'market':market,
              'label':'Hjemmeseier', 'price':1.7, 'probability':.65,'category':name}
        return {'localDate':'2026-11-03','generatedAt':'2026-11-03T08:17:00Z',
                'dataStatus':{'fixtures':'ok','odds':'ok'},
                'recommendations':[item], 'safeBets':[item], 'highRisk':[]}

    def test_results_do_not_change_original_odds(self):
        snapshot=lifecycle.with_initial_results(self.base())
        m={'id':1234,'status':'FINISHED', 'score':{'fullTime':{'home':2,'away':0}}}
        result,changed=lifecycle.apply_results(snapshot,[m],at='2026-11-03T22:00:00Z')
        self.assertTrue(changed)
        self.assertEqual(result['recommendations'][0]['result']['status'],'won')
        self.assertEqual(result['safeBets'][0]['result']['status'],'won')
        self.assertEqual(result['recommendations'][0]['price'],1.7)
        self.assertEqual(result['localDate'],'2026-11-03')
        self.assertEqual(result['editionDate'],'2026-11-03')

    def test_losing_goals_btts_and_draw(self):
        cases=[('H',1,2,False),('B',1,2,True),('U',1,1,True),('O25',1,1,False),
               ('U25',1,1,True),('O35',2,2,True),('BTTS',0,1,False)]
        for code,h,a,expected in cases:
            with self.subTest(market=code):
                self.assertEqual(lifecycle.pick_outcome(code,h,a), expected)

    def test_do_not_settle_on_live_or_missing_score(self):
        p={'market':'H', 'price':2.0}
        live=lifecycle.score_pick(p,{'status':'IN_PLAY','score':{'fullTime':{'home':1,'away':0}}})
        self.assertEqual(live['result']['status'],'live')
        self.assertNotEqual(live['result']['status'],'won')
        pending=lifecycle.score_pick(p,{'status':'FINISHED','score':{'fullTime':{'home':None,'away':None}}})
        self.assertEqual(pending['result']['status'],'unverified')

    def test_extra_time_settles_using_ninety_minutes(self):
        p={'market':'H','price':1.5}
        m={'status':'FINISHED','score':{'duration':'EXTRA_TIME',
           'regularTime':{'home':1,'away':1},'fullTime':{'home':2,'away':1}}}
        self.assertEqual(lifecycle.score_pick(p,m)['result']['status'],'lost')
        m['score'].pop('regularTime')
        self.assertEqual(lifecycle.score_pick(p,m)['result']['status'],'unverified')

    def test_no_results_does_not_clear_existing(self):
        snapshot=lifecycle.with_initial_results(self.base())
        updated,changed=lifecycle.apply_results(snapshot,[])
        self.assertFalse(changed)
        self.assertEqual(updated['recommendations'],snapshot['recommendations'])

    def test_cancelled_is_not_a_loss(self):
        p={'market':'H'}
        self.assertEqual(lifecycle.score_pick(p,{'status':'CANCELLED'})['result']['status'],'void')
        self.assertEqual(lifecycle.score_pick(p,{'status':'POSTPONED'})['result']['status'],'postponed')

    def test_unconfigured_feed_preserves_old_edition(self):
        with self.assertRaises(ValueError):
            lifecycle.create_edition({'localDate':'2026-11-04','dataStatus':{'fixtures':'error','odds':'ok'}},
                                     self.base(), '')

    def test_archive_name_and_score_are_consistent(self):
        p=lifecycle.with_initial_results(self.base())
        self.assertEqual(p['editionDate'],'2026-11-03')
        self.assertEqual(p['recommendations'][0]['result']['status'],'scheduled')

if __name__=='__main__':unittest.main()
