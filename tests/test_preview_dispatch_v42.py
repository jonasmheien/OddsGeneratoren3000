"""Tests that late scheduled preview dispatches cannot miss a narrow minute window."""
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from rollover_v26 import is_due
OSLO=ZoneInfo('Europe/Oslo')

class PreviewDispatchV42(unittest.TestCase):
    def test_preview_starts_even_if_github_dispatch_is_late(self):
        active={'editionDate':'2026-11-09','safeBets':[{'kickoff':'2026-11-09T19:30:00+01:00'}]}
        now=datetime(2026,11,9,21,37,tzinfo=OSLO)
        self.assertTrue(is_due(active,None,now,hourly=False))
        self.assertFalse(is_due(active,None,now,hourly=True))
        self.assertFalse(is_due(active,{'previewEdition':True,'editionDate':'2026-11-10'},now,hourly=False))

    def test_dont_build_while_last_match_not_started(self):
        active={'editionDate':'2026-11-09','highRisk':[{'kickoff':'2026-11-09T22:15:00+01:00'}]}
        self.assertFalse(is_due(active,None,datetime(2026,11,9,21,47,tzinfo=OSLO),hourly=False))

    def test_preview_schedules_and_monitor_hook_are_present(self):
        wf=(ROOT/'.github/workflows/publish.yml').read_text()
        for stamp in ('07 21','07 22','07 23'):
            self.assertIn("cron: '"+stamp+" * * *'",wf)
        self.assertIn('rollover_v26.py --due --broad-window',wf)
        self.assertIn('python scripts/quality_monitor_v42.py',wf)
        self.assertIn('site/data/performance-v42.json',wf)

if __name__=='__main__':unittest.main()
