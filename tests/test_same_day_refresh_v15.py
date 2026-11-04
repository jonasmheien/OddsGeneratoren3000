"""Safety checks for one-off refresh on v1.5 upload."""
from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=(ROOT/'.github/workflows/publish.yml').read_text(encoding='utf-8')
sys.path.insert(0,str(ROOT/'scripts'))
import lifecycle

class SameDayRefreshTests(unittest.TestCase):
    def test_opt_in_file_is_shipped(self):
        if (ROOT/'.github/refresh-once-v15').exists():
            self.assertEqual((ROOT/'.github/refresh-once-v15').read_text().strip(),'REFRESH_ON_NEXT_PUSH')

    def test_code_push_can_generate_new_day(self):
        self.assertIn('echo "mode=daily" >> "$GITHUB_OUTPUT"',WORKFLOW)
        self.assertIn('refresh_on_push=true',WORKFLOW)
        self.assertIn('refresh_on_push=false',WORKFLOW)
        self.assertIn('grep -qx',WORKFLOW)

    def test_existing_tips_are_explicitly_replaced_only_when_requested(self):
        self.assertIn("steps.trigger.outputs.refresh_on_push == 'true'",WORKFLOW)
        self.assertIn('FORCE_REPLACE_EDITION:',WORKFLOW)
        self.assertIn("inputs.mode == 'daily'",WORKFLOW)

    def test_one_time_refresh_flag_removed_after_success(self):
        self.assertIn("if [[ \"${MODE}\" == 'daily' ]] && [[ -f .github/refresh-once-v15 ]]; then",WORKFLOW)
        self.assertIn('git rm -f -- .github/refresh-once-v15',WORKFLOW)
        self.assertIn("git add -A -- state/ site/data/today.json site/data/history.json",WORKFLOW)

    def test_explicit_refresh_actually_replaces_same_day_locked_edition(self):
        old={'localDate':'2026-11-04','generatedAt':'old','dataStatus':{'fixtures':'ok','odds':'ok'},
             'coverage':{'upcomingMatches':3,'matchedOdds':3},'recommendations':[],'safeBets':[],'highRisk':[]}
        new={**old,'generatedAt':'new'}
        prior=lifecycle.with_initial_results(old)
        self.assertIs(lifecycle.create_edition(new,prior,''),prior)
        with patch.dict(os.environ,{'FORCE_REPLACE_EDITION':'1'}):
            changed=lifecycle.create_edition(new,prior,'')
        self.assertEqual(changed['generatedAt'],'new')
        self.assertTrue(changed['editionLocked'])

    def test_existing_schedule_remains(self):
        self.assertIn("cron: '17 9 * * *'",WORKFLOW)
        self.assertIn("timezone: 'Europe/Oslo'",WORKFLOW)

if __name__=='__main__':unittest.main()
