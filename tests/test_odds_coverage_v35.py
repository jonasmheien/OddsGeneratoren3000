"""v35 regression: broaden one push only; fixture aliases must not merge distinct games."""
import os
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_data
from build_data import affordable_sports
from odds_first_v25 import fixtures_from_quotes

class ExtraCoverageV35(unittest.TestCase):
    def test_low_quota_prioritizes_first_daily_edition(self):
        now = datetime(2026, 11, 14, 8, 49, tzinfo=timezone.utc)
        sports = ['soccer_uefa_nations_league', 'soccer_efl_champ']
        with patch('build_data.load_edition', return_value=None):
            self.assertEqual(affordable_sports(sports, 54, now), sports[:1])
            self.assertEqual(affordable_sports(sports, 2, now), sports[:1])
            self.assertEqual(affordable_sports(sports, 1, now), [])
            self.assertEqual(affordable_sports(sports, 58, now), sports)
            self.assertEqual(affordable_sports(sports, 20, now, preview=True), [])
        edition = {'editionDate': '2026-11-14', 'generatedAt': now.isoformat()}
        with patch('build_data.load_edition', return_value=edition):
            self.assertEqual(affordable_sports(sports, 54, now), [])

    def test_low_quota_defers_refresh_through_existing_workflow_scripts(self):
        now = datetime.now(build_data.OSLO).replace(hour=12, minute=0, second=0, microsecond=0)
        day = now.date().isoformat()
        previous = {'localDate': day, 'editionDate': day, 'generatedAt': now.isoformat(),
                    'editionLocked': True, 'dataStatus': {'fixtures': 'ok', 'odds': 'ok'},
                    'recommendations': [], 'safeBets': [], 'highRisk': []}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'state' / 'active.json'
            public = root / 'site' / 'data' / 'today.json'
            candidate = state.with_name('.candidate.json')
            for output in (state, public):
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(previous), encoding='utf-8')
            env = {'ODDS_API_KEY': 'test-key', 'FOOTBALL_DATA_API_KEY': 'test-fixtures',
                   'ODDS_SPORTS': 'soccer_uefa_nations_league', 'ODDS_OUTPUT_PATH': str(candidate)}
            with (patch.dict(os.environ, env, clear=True),
                  patch.object(build_data, 'ROOT', root), patch.object(build_data, 'OUT', candidate),
                  patch.object(build_data, 'load_edition', return_value=previous),
                  patch.object(build_data, 'odds_remaining', return_value=50),
                  patch.object(build_data, 'discover_sportmonks', return_value=([], {'state': 'ok'})),
                  patch.object(build_data, 'fetch_json', return_value={'matches': []}) as fetch,
                  patch.object(build_data, 'datetime') as clock):
                clock.now.return_value = now
                build_data.main()
                fetch.assert_called_once()
            before = candidate.read_bytes()
            for script in ('market_scan_v14.py', 'score_consensus_v14.py', 'qualify_v20.py'):
                subprocess.run([sys.executable, 'scripts/' + script, str(candidate)], cwd=ROOT, check=True)
            self.assertEqual(candidate.read_bytes(), before)
            code = ('import sys; from pathlib import Path; import lifecycle; '
                    'lifecycle.STATE, lifecycle.PUBLIC = map(Path, sys.argv[1:3]); '
                    'lifecycle.publish_history = lambda _: None; '
                    'lifecycle.fetch_results = lambda *args: []; '
                    'sys.argv = ["lifecycle.py", "daily"]; lifecycle.main()')
            out = subprocess.check_output([sys.executable, '-c', code, str(state), str(public)],
                                          env=dict(os.environ, PYTHONPATH=str(ROOT / 'scripts'),
                                                   ODDS_OUTPUT_PATH=str(candidate), FORCE_REPLACE_EDITION='1'),
                                          text=True)
            self.assertIn('ODDS_REFRESH_DEFERRED', out)
            self.assertIn('RESULTS_CHANGED=0', out)
            self.assertFalse(candidate.exists())
            self.assertEqual(json.loads(public.read_text()), previous)
            self.assertEqual(json.loads(state.read_text()), previous)

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
