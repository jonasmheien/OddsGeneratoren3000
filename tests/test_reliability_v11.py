"""Guardrails for tomorrow's actual GitHub Actions daily analysis."""
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import lifecycle
from build_data import build_snapshot


class DailyReliabilityTests(unittest.TestCase):
    def candidate(self, upcoming=2, priced=1, odds_state='ok'):
        return {
            'localDate': '2026-11-04', 'generatedAt': '2026-11-04T08:17:00+00:00',
            'dataStatus': {'fixtures':'ok','odds':odds_state},
            'coverage': {'upcomingMatches': upcoming, 'matchedOdds': priced},
            'recommendations': [], 'safeBets': [], 'highRisk': [],
        }

    def test_failed_bookmaker_match_cannot_publish_empty_day(self):
        with self.assertRaisesRegex(ValueError, 'No upcoming matches linked'):
            lifecycle.create_edition(self.candidate(priced=0), None, '')

    def test_missing_bookmaker_feed_cannot_publish(self):
        for status in ('empty','error','not_configured'):
            with self.subTest(status=status):
                with self.assertRaises(ValueError):
                    lifecycle.create_edition(self.candidate(odds_state=status), None, '')

    def test_missing_fixture_feed_cannot_publish(self):
        data=self.candidate()
        data['dataStatus']['fixtures']='error'
        with self.assertRaises(ValueError):
            lifecycle.create_edition(data, None, '')

    def test_real_odds_without_qualified_picks_is_valid_screening(self):
        edition=lifecycle.create_edition(self.candidate(), None, '')
        self.assertTrue(edition['editionLocked'])
        self.assertEqual(edition['recommendations'],[])

    def test_zero_upcoming_matches_can_create_honest_empty_edition(self):
        edition=lifecycle.create_edition(self.candidate(upcoming=0,priced=0,odds_state='empty'),None,'')
        self.assertEqual(edition['editionDate'],'2026-11-04')

    def test_same_day_retry_does_not_replace_selections_or_odds(self):
        previous=lifecycle.with_initial_results(self.candidate())
        previous['recommendations']=[{'market':'H','price':2.04,'result':{'status':'won'}}]
        new=self.candidate()
        new['recommendations']=[{'market':'H','price':1.40}]
        again=lifecycle.create_edition(new,previous,'')
        self.assertEqual(again,previous)
        self.assertEqual(again['recommendations'][0]['price'],2.04)

    def test_valid_published_snapshot_recovers_if_state_file_missing(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'today.json'
            import json
            p.write_text(json.dumps(lifecycle.with_initial_results(self.candidate())))
            with patch.object(lifecycle, 'PUBLIC', p):
                restored=lifecycle.published_edition_fallback()
            self.assertEqual(restored['editionDate'],'2026-11-04')

    def test_bundled_placeholder_never_becomes_active(self):
        with tempfile.TemporaryDirectory() as td:
            import json
            p=Path(td)/'today.json'
            p.write_text(json.dumps({'localDate':'2026-11-02','dataStatus':{'fixtures':'not_configured'}}))
            with patch.object(lifecycle,'PUBLIC',p):
                self.assertIsNone(lifecycle.published_edition_fallback())

    def test_generated_diagnostics_explain_when_everything_is_filtered(self):
        now=datetime(2026,11,4,8,17,tzinfo=timezone.utc)
        fake=[]
        result=build_snapshot(now,fake,[],[],[],{'fixtures':'ok','odds':'empty'})
        self.assertEqual(result['coverage']['matchedOdds'],0)

    def test_workflow_retries_and_does_not_recompute_on_code_push(self):
        workflow=(ROOT/'.github/workflows/publish.yml').read_text()
        self.assertIn("cron: '17 10 * * *'", workflow)
        self.assertIn("cron: '17 11 * * *'", workflow)
        self.assertIn('python scripts/morning_refresh_v29.py --due',workflow)
        # By default a code push deploys the stored edition. The explicit
        # one-time v1.5 release marker is the sole exception.
        self.assertIn('if [[ "$EVENT" == "push" ]]; then',workflow)
        self.assertIn('echo "mode=deploy" >> "$GITHUB_OUTPUT"',workflow)
        self.assertIn("grep -qx 'REFRESH_ON_NEXT_PUSH'",workflow)
        self.assertIn('ODDS_OUTPUT_PATH: state/.candidate.json',workflow)
        self.assertIn('git add -A -- state/ site/data/today.json site/data/history.json',workflow)


if __name__=='__main__':unittest.main()
