import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from odds_first_v25 import preview_sports, fixtures_from_quotes

NOW = datetime(2026, 11, 4, 20, 42, tzinfo=timezone.utc)
TOMORROW = date(2026, 11, 5)


def event(*, sport='soccer_uefa_europa_league', at='2026-11-05T17:45:00Z',
          eid='ab0123456789', home='AC Milan', away='Ferencvaros', quote=True):
    return {'id': eid, 'sport_key': sport, 'commence_time': at,
            'home_team': home, 'away_team': away, 'bookmakers': (
                [{'markets': [{'key': 'h2h', 'outcomes': [{'name': home, 'price': 1.78}]}]}]
                if quote else [])}


class OddsFirstPreviewTests(unittest.TestCase):
    def test_unlisted_europa_leagues_added_to_preview(self):
        self.assertEqual(preview_sports([], max_sports=2), [
            'soccer_uefa_europa_league', 'soccer_uefa_europa_conference_league'])

    def test_known_league_not_duplicated(self):
        self.assertEqual(preview_sports(['soccer_uefa_europa_league'], max_sports=2), [
            'soccer_uefa_europa_league', 'soccer_uefa_europa_conference_league'])

    def test_actual_bookmaker_event_becomes_unmodelled_fixture(self):
        items=fixtures_from_quotes([event()], NOW, TOMORROW)
        self.assertEqual(len(items),1)
        self.assertTrue(items[0]['id'].startswith('odds:'))
        self.assertEqual(items[0]['competition']['code'],'ODDS-EL')
        self.assertIsNone(items[0]['score']['fullTime']['home'])
        self.assertNotIn('model',items[0])

    def test_does_not_admit_no_odds_or_wrong_date_or_past(self):
        items=[event(eid='noodds111',quote=False),
               event(eid='tomorrow11',at='2026-11-06T17:45:00Z'),
               event(eid='pastday000',at='2026-11-04T17:45:00Z')]
        self.assertEqual(fixtures_from_quotes(items,NOW,TOMORROW),[])

    def test_reject_malformed_and_nonfootball(self):
        items=[event(sport='basketball_nba'),
               event(eid='bad id?'),
               event(eid='short'),
               event(eid='same001234',home='Milan',away='Milan')]
        self.assertEqual(fixtures_from_quotes(items,NOW,TOMORROW),[])

    def test_bookmaker_duplicates_are_removed(self):
        ev=event()
        self.assertEqual(len(fixtures_from_quotes([ev,ev],NOW,TOMORROW)),1)

    def test_does_not_duplicate_existing_official_fixture(self):
        other={'utcDate':'2026-11-05T17:45:00Z',
               'homeTeam':{'name':'AC Milan'},'awayTeam':{'name':'Ferencvaros'}}
        self.assertEqual(fixtures_from_quotes([event()], NOW, TOMORROW, [other]),[])

    def test_timezone_is_oslo_for_match_date(self):
        self.assertEqual(fixtures_from_quotes([event(at='2026-11-04T23:15:00Z')], NOW, TOMORROW)[0]['id'],
                         'odds:ab0123456789')

if __name__ == '__main__':
    unittest.main()
