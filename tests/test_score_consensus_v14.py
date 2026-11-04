"""Offline tests for source-based exact-score consensus."""
import csv
import sys
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
import score_consensus_v14 as s

AT=datetime(2026,11,4,8,30,tzinfo=timezone.utc)
KICK=(AT+timedelta(hours=12)).isoformat()


def fixture():
    return {'id':'123','home':'Liverpool','away':'Real Madrid',
            'kickoff':KICK,'status':'SCHEDULED','league':'Champions League',
            'model':{'expectedGoals':[2.1,1.3],'sample':[6,6]}}


def prediction(source,home,away,host=None):
    return {'source':source,'source_url':f'https://{host or source.lower()}.com/fixture',
            'date':'2026-11-04','home':'Liverpool','away':'Real Madrid','match_id':'123',
            'home_goals':str(home),'away_goals':str(away),'observed_at':(AT-timedelta(hours=1)).isoformat()}


class ConsensusTests(unittest.TestCase):
    def test_exact_score_values_not_betting_thresholds(self):
        self.assertEqual(s.exact_goals('2'),2)
        for bad in ('+1.5','-1.5','Over 2.5','2-1',2.5,'8.5',-1,9,True,None):
            self.assertIsNone(s.exact_goals(bad))

    def test_domain_is_credible_and_https(self):
        self.assertTrue(s.safe_source(prediction('Vitibet',2,1)))
        self.assertIsNone(s.safe_source(prediction('Vitibet',2,1,'fake-vitibet.org')))
        self.assertIsNone(s.safe_source(prediction('AnotherSite',2,1)))
        self.assertFalse(s.trusted_url('http://vitibet.com/scores',('vitibet.com',)))
        self.assertFalse(s.trusted_url('https://vitibet.com.evil.org/scores',('vitibet.com',)))

    def test_consensus_is_equal_weight_average(self):
        picks=[s.safe_source(prediction('Vitibet',2,1)),s.safe_source(prediction('Forebet',1,1))]
        sources,combined=s.aggregate_sources(picks)
        self.assertEqual((combined['homeGoals'],combined['awayGoals']),(2,1))
        self.assertEqual(combined['sourceCount'],2)
        self.assertEqual(len(sources),2)
        self.assertIsNone(s.aggregate_sources(picks[:1])[1])

    def test_duplicate_forebet_does_not_gain_extra_weight(self):
        a=s.safe_source(prediction('Forebet',2,1))
        b=s.safe_source(prediction('Vitibet',1,0))
        unique,c=s.aggregate_sources([a,a,b])
        self.assertEqual(len(unique),2)
        self.assertEqual(c['sourceCount'],2)
        conflict=s.safe_source(prediction('Forebet',5,0))
        unique,c=s.aggregate_sources([a,conflict,b])
        self.assertEqual(len(unique),1)
        self.assertIsNone(c)

    def test_csv_matches_both_teams_and_fresh_observations(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'scores.csv'
            with p.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(prediction('Vitibet',2,1)))
                writer.writeheader();writer.writerow(prediction('Vitibet',2,1))
                invalid=prediction('Forebet',1,1)
                invalid['away']='Chelsea';writer.writerow(invalid)
            found,issues=s.load_csv_rows(p,[fixture()],AT)
            self.assertEqual(len(found['123']),1)
            self.assertTrue(issues)

    def test_model_is_always_distinct_from_external_consensus(self):
        s0={'matches':[fixture()],'recommendations':[{'matchId':'123'}],
            'safeBets':[],'highRisk':[]}
        with patch.object(s,'fetch_api_football',return_value=({},[])):
            x=s.build(s0,AT,Path('/definitely/not/a/file.csv'))
        game=x['scorePredictions']['games'][0]
        self.assertIsNone(game['consensus'])
        self.assertIsNotNone(game['ownModel'])
        self.assertEqual(game['sources'],[])

    def test_injected_api_forecast_can_combine_with_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'scores.csv'
            with file.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(prediction('Vitibet',2,1)))
                writer.writeheader();writer.writerow(prediction('Vitibet',2,1))
            api={'123':[{'source':'API-Football Predictions','sourceUrl':'https://www.api-football.com/',
                         'homeGoals':1,'awayGoals':1,'observedAt':AT.isoformat()}]}
            with patch.object(s,'fetch_api_football',return_value=(api,[])):
                x=s.build({'matches':[fixture()],'recommendations':[{'matchId':'123'}]},AT,file,'KEY')
            result=x['scorePredictions']['games'][0]
            self.assertEqual(len(result['sources']),2)
            self.assertEqual((result['consensus']['homeGoals'],result['consensus']['awayGoals']),(2,1))

    def test_api_skips_range_not_exact_score(self):
        self.assertIsNone(s.exact_goals('-2.5'))
        self.assertIsNone(s.exact_goals('1.5'))


if __name__=='__main__':unittest.main()
