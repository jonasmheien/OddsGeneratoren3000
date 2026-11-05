"""Morning schedule must replace an early draft exactly once."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from morning_refresh_v29 import should_refresh


class MorningRefreshV29Tests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 5, 9, 17, tzinfo=timezone.utc)  # 10:17 Oslo
        self.early = {'editionDate':'2026-11-05', 'generatedAt':'2026-11-05T08:08:00Z'}

    def test_early_same_day_edition_does_not_suppress_morning(self):
        self.assertTrue(should_refresh(self.early, self.now))

    def test_finished_morning_edition_is_not_rerun(self):
        edition = {'editionDate':'2026-11-05', 'generatedAt':'2026-11-05T08:22:00Z'}
        self.assertFalse(should_refresh(edition, self.now))

    def test_missing_today_allows_new_edition(self):
        self.assertTrue(should_refresh({'editionDate':'2026-11-04'}, self.now))

    def test_outside_morning_does_not_use_odds_credits(self):
        self.assertFalse(should_refresh(self.early, datetime(2026,11,5,13,20,tzinfo=timezone.utc)))

    def test_malformed_timestamp_requires_retry(self):
        self.assertTrue(should_refresh({'editionDate':'2026-11-05', 'generatedAt':'?'} , self.now))


if __name__ == '__main__':
    unittest.main()
