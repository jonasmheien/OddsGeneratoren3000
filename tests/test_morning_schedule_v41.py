"""Frozen-clock regression tests for earlier morning launch with no repeat credits."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from morning_refresh_v29 import should_refresh

class MorningScheduleV41(unittest.TestCase):
    def test_after_0907_snapshot_blocks_duplicate_morning_requests(self):
        # First 09:07 Oslo morning run finishes at 09:09 Oslo.
        edition={'editionDate':'2026-11-07','generatedAt':'2026-11-07T08:09:00Z'}
        now=datetime(2026,11,7,9,17,tzinfo=timezone.utc) # 10:17 Oslo
        self.assertFalse(should_refresh(edition,now))
    def test_yesterday_or_early_preview_still_requires_new_analysis(self):
        now=datetime(2026,11,7,9,17,tzinfo=timezone.utc)
        yesterday={'editionDate':'2026-11-06','generatedAt':'2026-11-06T15:00:00Z'}
        preview={'editionDate':'2026-11-07','generatedAt':'2026-11-07T07:50:00Z'}
        self.assertTrue(should_refresh(yesterday,now))
        self.assertTrue(should_refresh(preview,now))
    def test_late_evening_does_not_reopen_morning_fallback(self):
        earlier={'editionDate':'2026-11-06','generatedAt':'2026-11-06T15:00:00Z'}
        self.assertFalse(should_refresh(earlier,datetime(2026,11,7,15,25,tzinfo=timezone.utc)))
    def test_workflow_has_new_times_with_oslo_timezone(self):
        wf=(Path(__file__).resolve().parents[1]/'.github/workflows/publish.yml').read_text()
        for time in ('07 9','17 9','37 9','17 13','17 16','17 19'):
            self.assertIn("cron: '"+time+" * * *'",wf)
        self.assertIn('low_volume',wf)
        # v35 compatibility: retain the approved one-shot nine-league analysis
        # and normal four-league coverage while reducing midday API usage.
        self.assertIn("refresh_on_push == 'true' && '9'", wf)
        self.assertIn("(steps.trigger.outputs.mode == 'tomorrow' && '2' || '4')", wf)
        self.assertIn("refresh_on_schedule=true",wf)

if __name__=='__main__':unittest.main()
