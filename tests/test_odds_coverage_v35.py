"""v35 regression: broaden one push only; fixture aliases must not merge distinct games."""
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from odds_first_v25 import fixtures_from_quotes

class ExtraCoverageV35(unittest.TestCase):
    def test_one_shot_nine_leagues_and_ordinary_four(self):
        wf=(ROOT/'.github/workflows/publish.yml').read_text()
        self.assertIn("refresh_on_push == 'true' && '9'",wf)
        self.assertIn("(steps.trigger.outputs.mode == 'tomorrow' && '2' || '4')",wf)
        cmd=[sys.executable,'-c',"import sys;sys.path.insert(0,'scripts');import build_data;print(build_data.ODDS_SPORTS_PER_RUN)"]
        env=os.environ.copy();env['ODDS_SPORTS_PER_RUN']='9'
        self.assertEqual(subprocess.check_output(cmd,cwd=ROOT,env=env,text=True).strip(),'9')
        env['ODDS_SPORTS_PER_RUN']='4'
        self.assertEqual(subprocess.check_output(cmd,cwd=ROOT,env=env,text=True).strip(),'4')

    def test_bolton_wanderers_and_bolton_are_same_fixture(self):
        self._check('Bolton', 'Bolton Wanderers', 'Derby County', 'Derby County')

    def test_silkeborg_name_alias(self):
        self._check('Lyngby','Lyngby','Silkeborg','Silkeborg IF')

    def test_do_not_merge_different_opponents(self):
        self._check('Bolton','Bolton Wanderers','Derby County','Sheffield United',expected=1)

    def _check(self,known_away,quote_away,known_home,quote_home,expected=0):
        now=datetime(2026,11,6,11,0,tzinfo=timezone.utc)
        ko='2026-11-06T20:00:00Z'
        existing=[{'id':4567,'status':'SCHEDULED','utcDate':ko,
                   'homeTeam':{'id':100,'name':known_home,'shortName':known_home},
                   'awayTeam':{'id':101,'name':known_away,'shortName':known_away}}]
        evt={'id':'test-valid1234','sport_key':'soccer_efl_champ',
             'home_team':quote_home,'away_team':quote_away,'commence_time':ko,
             'bookmakers':[{'markets':[{'key':'h2h','outcomes':[{'price':2.4}]}]}]}
        found=fixtures_from_quotes([evt],now,now.date(),existing)
        self.assertEqual(len(found),expected)

if __name__=='__main__':unittest.main()
