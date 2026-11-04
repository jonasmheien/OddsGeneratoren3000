"""Regression tests for automatic rollover without touching public data."""
import unittest
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from rollover_v26 import is_due,visible_kickoffs

OSLO=ZoneInfo('Europe/Oslo')
def time(hour,minute=0):return datetime(2026,11,5,hour,minute,tzinfo=OSLO)
def basic(kickoffs=None):
    return {'editionDate':'2026-11-05','recommendations':[{'kickoff':x.isoformat()} for x in (kickoffs or [])],'matches':[]}

class RolloverV26(unittest.TestCase):
    def test_after_final_shown_kickoff(self):
        snap=basic([time(17,45),time(19,30)])
        self.assertFalse(is_due(snap,None,time(19,0)))
        self.assertTrue(is_due(snap,None,time(20,1)))
    def test_not_every_ten_minutes_consumes_credits(self):
        self.assertFalse(is_due(basic([time(14)]),None,time(20,20)))
    def test_existing_tomorrow_prevents_duplicate(self):
        preview={'previewEdition':True,'editionDate':'2026-11-06'}
        self.assertFalse(is_due(basic([time(17)]),preview,time(20,0)))
    def test_old_day_does_not_jump_another_day(self):
        old=basic([time(17)]);old['editionDate']='2026-11-04'
        self.assertFalse(is_due(old,None,time(20,0)))
    def test_without_picks_use_bookmaker_backed_games(self):
        snap=basic();snap['matches']=[{'kickoff':time(19,45).isoformat(),'odds':{'H':{'price':2}}}]
        self.assertFalse(is_due(snap,None,time(19,0)))
        self.assertTrue(is_due(snap,None,time(20,0)))
    def test_blank_day_evening_fallback(self):
        self.assertFalse(is_due(basic(),None,time(12,0)))
        self.assertTrue(is_due(basic(),None,time(18,0)))
    def test_midnight_never_previews_day_after_tomorrow(self):
        self.assertFalse(is_due(basic([time(17)]),None,time(0,0)))
    def test_date_parsing_preserves_timezone(self):
        snap=basic([time(19,45)])
        self.assertEqual(visible_kickoffs(snap,time(20)),[time(19,45).astimezone(timezone.utc)])

if __name__=='__main__':unittest.main()
