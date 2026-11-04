"""Zero-network regression tests of v2.0 conservative selection and diagnostics."""
import sys
import unittest
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from quality_v20 import assess, screen, overlaps, fresh_quote
from qualify_v20 import qualify
from backtest_v20 import evaluate

NOW=datetime(2026,11,4,8,17,tzinfo=timezone.utc)

def q(price=2.20,books=3,hours=1):
    return {'price':price,'books':books,'lastUpdated':(NOW-timedelta(hours=hours)).isoformat()}

def fixture(i=1, p=.60, sample=8):
    return {'id':str(i),'home':'Hjemme','away':'Borte','league':'Testliga',
            'kickoff':(NOW+timedelta(hours=7)).isoformat(),'status':'SCHEDULED',
            'model':{'quality':'basic','sample':[sample,sample],
                     'probabilities':{'H':p}},'odds':{'H':q()},'predictions':[]}

class RiskAwareScreeningTests(unittest.TestCase):
    def test_good_candidate_has_a_positive_adjusted_edge(self):
        m=fixture()
        result=screen(m,'H',NOW)
        self.assertIsNotNone(result)
        self.assertGreater(result['conservativeEdge'],.02)
        self.assertLess(result['conservativeProbability'],m['model']['probabilities']['H'])
        self.assertAlmostEqual(result['conservativeEdge'],result['conservativeProbability']*2.2-1,delta=.001)

    def test_model_outlier_is_rejected_even_when_nominal_edge_is_massive(self):
        m=fixture(p=.92)
        self.assertIsNone(screen(m,'H',NOW))

    def test_missing_history_never_qualifies(self):
        self.assertIsNone(screen(fixture(sample=3),'H',NOW))
        self.assertIsNone(screen(fixture(sample=4),'H',NOW))

    def test_one_bookmaker_requires_stronger_history(self):
        m=fixture(sample=6);m['odds']['H']=q(2.2,books=1)
        self.assertIsNone(screen(m,'H',NOW))
        m['model']['sample']=[14,14]
        self.assertIsNotNone(screen(m,'H',NOW))

    def test_nan_stale_or_unverified_quotes_rejected(self):
        m=fixture();m['odds']['H']=q(float('nan'))
        self.assertIsNone(screen(m,'H',NOW))
        m['odds']['H']=q(hours=7)
        self.assertIsNone(screen(m,'H',NOW))
        m['odds']['H']=q()
        m['odds']['H'].pop('lastUpdated')
        self.assertIsNone(screen(m,'H',NOW))

    def test_bookmaker_only_favourite_is_not_recommended(self):
        m=fixture()
        m['model']=None
        self.assertEqual(qualify({'generatedAt':NOW.isoformat(),'matches':[m]})['recommendations'],[])

    def test_external_disagreement_cannot_increase_value(self):
        plain=screen(fixture(),'H',NOW)
        m=fixture();m['predictions']=[{'source':'Example','probabilities':{'H':.15}}]
        disputed=screen(m,'H',NOW)
        if disputed is None:
            self.assertTrue(plain is not None)
        else:
            self.assertLess(disputed['conservativeEdge'],plain['conservativeEdge'])

    def test_up_to_two_independent_markets_same_match(self):
        m=fixture()
        m['model']['probabilities']['O25']=.70
        m['odds']['O25']=q(2.0)
        d=qualify({'generatedAt':NOW.isoformat(),'matches':[m]})
        self.assertEqual(len(d['recommendations']),2)
        self.assertEqual({p['market'] for p in d['recommendations']},{'H','O25'})
        self.assertFalse(overlaps('H','COO95'))
        self.assertTrue(overlaps('O25','U25'))
        self.assertTrue(overlaps('H','THO15'))

    def test_no_quota_or_forced_minimum_of_picks(self):
        data={'generatedAt':NOW.isoformat(),'matches':[fixture(i) for i in range(12)]}
        result=qualify(data)
        self.assertEqual(len(result['recommendations']),12)
        self.assertEqual(result['modelVersion'],'2.0-foundation')
        self.assertEqual(result['safeBets'],[])
        self.assertEqual(result['highRisk'],[])
        data={'generatedAt':NOW.isoformat(),'matches':[]}
        self.assertEqual(qualify(data)['recommendations'],[])

    def test_observation_is_not_mistaken_for_recommendation(self):
        m=fixture(sample=3)
        d=qualify({'generatedAt':NOW.isoformat(),'matches':[m]})
        self.assertFalse(d['recommendations'])
        self.assertEqual(d['observations'][0]['status'],'observation')

    def test_special_market_without_data_cannot_be_qualified(self):
        m=fixture()
        d=qualify({'generatedAt':NOW.isoformat(),'matches':[m],
                   'additionalMarkets':{'tips':[], 'watchlist':[{
                      'matchId':str(m['id']),'market':'COO95', 'label':'Over 9,5 hjørnespark',
                      'marketType':'corners', 'price':2.1, 'bookmakers':1,
                      'oddsUpdatedAt':q()['lastUpdated'],'probability':None, 'sampleSize':0}]}})
        self.assertTrue(all(x['market']!='COO95' for x in d['recommendations']))
        self.assertTrue(all(x['market']!='COO95' for x in d['observations']))

    def test_observations_do_not_show_both_sides_of_same_line(self):
        m=fixture(sample=3)
        m['model']['probabilities'].update({'O25':.60,'U25':.60})
        m['odds'].update({'O25':q(2.0),'U25':q(2.0)})
        d=qualify({'generatedAt':NOW.isoformat(),'matches':[m]})
        self.assertLessEqual(sum(x['market'] in ('O25','U25') for x in d['observations']),1)

    def test_workflow_qualifies_only_new_daily_candidates(self):
        yaml=(ROOT/'.github/workflows/publish.yml').read_text()
        self.assertIn('python scripts/qualify_v20.py state/.candidate.json',yaml)
        self.assertIn("if: steps.trigger.outputs.mode == 'daily'",yaml)
        self.assertLess(yaml.index('python scripts/score_consensus_v14.py state/.candidate.json'),
                        yaml.index('python scripts/qualify_v20.py state/.candidate.json'))
        self.assertLess(yaml.index('python scripts/qualify_v20.py state/.candidate.json'),
                        yaml.index('python scripts/lifecycle.py "$MODE"'))

    def test_selected_picks_are_compatible_with_existing_settlement(self):
        import lifecycle
        d=qualify({'generatedAt':NOW.isoformat(),'localDate':'2026-11-04',
                   'matches':[fixture()]})
        prepared=lifecycle.with_initial_results(d)
        self.assertEqual(prepared['recommendations'][0]['result']['status'],'scheduled')
        self.assertIn('conservativeEdge',prepared['recommendations'][0])
        self.assertEqual(prepared['editionDate'],'2026-11-04')

    def test_versioned_source_files_exist(self):
        html=(ROOT/'site/index.html').read_text()
        self.assertIn('quality-v20.js?v=20',html)
        self.assertIn('quality-v20.css?v=20',html)
        js=(ROOT/'site/quality-v20.js').read_text()
        self.assertIn('v20-active',js)
        self.assertIn('Ikke anbefalt',js)

    def test_backtest_deduplicates_and_rejects_unsettled(self):
        pick={'matchId':'1','market':'H','price':2,'probability':.6,'result':{'status':'won'}}
        stale={'matchId':'2','market':'O25','price':2,'result':{'status':'scheduled'}}
        result=evaluate([{'editionDate':'2026-11-04','recommendations':[pick,stale],
                          'safeBets':[pick]}])
        self.assertEqual(result['overall']['settled'],1)
        self.assertEqual(result['overall']['flatStakeROI'],1)
        self.assertTrue(result['overall']['insufficientSample'])

if __name__=='__main__':unittest.main()
