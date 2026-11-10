import copy
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from tomorrow_v24 import publish_preview, validate_preview


class TomorrowPreviewTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 4, 21, 30, tzinfo=timezone.utc)
        self.snapshot = {
            'localDate': '2026-11-05', 'dataStatus': {'fixtures': 'ok', 'odds': 'ok'},
            'coverage': {'matchedOdds': 2},
            'matches': [{'id':'1'}],
            'recommendations': [{'kickoff':'2026-11-05T20:00:00+00:00','market':'H'}],
        }

    def test_tomorrow_publishes_without_touching_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            current = directory / 'today.json'
            current.write_text('ORIGINAL', encoding='utf-8')
            destination = directory / 'tomorrow.json'
            publish_preview(self.snapshot, self.now, destination)
            self.assertEqual(current.read_text(encoding='utf-8'), 'ORIGINAL')
            import json
            result = json.loads(destination.read_text(encoding='utf-8'))
            self.assertTrue(result['previewEdition'])
            self.assertEqual(result['editionDate'], '2026-11-05')
            self.assertFalse(result['editionLocked'])

    def test_rejects_current_day(self):
        obj = copy.deepcopy(self.snapshot)
        obj['localDate'] = '2026-11-04'
        with self.assertRaisesRegex(ValueError,'Wrong preview date'):
            validate_preview(obj, self.now)

    def test_rejects_no_bookmaker_odds(self):
        obj=copy.deepcopy(self.snapshot)
        obj['coverage']['matchedOdds'] = 0
        with self.assertRaisesRegex(ValueError, 'No matching'):
            validate_preview(obj,self.now)

    def test_rejects_invalid_picks(self):
        obj=copy.deepcopy(self.snapshot)
        obj['recommendations'][0].pop('market')
        with self.assertRaisesRegex(ValueError, 'Invalid recommended'):
            validate_preview(obj,self.now)

    def test_preview_without_odds_is_not_published(self):
        obj = copy.deepcopy(self.snapshot)
        obj["coverage"]["matchedOdds"] = 0
        with self.assertRaisesRegex(ValueError, "No matching"):
            validate_preview(obj, self.now)

    def test_near_midnight_oslo(self):
        obj=copy.deepcopy(self.snapshot)
        obj['localDate']='2026-11-06'
        validate_preview(obj,datetime(2026,11,4,23,5,tzinfo=timezone.utc))


if __name__ == '__main__':
    unittest.main()
