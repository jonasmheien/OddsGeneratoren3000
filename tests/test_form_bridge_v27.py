"""Offline safety checks for the official-results form bridge."""
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'scripts'))
from form_bridge_v27 import bridge, load_free_history, valid_finished

NOW = datetime(2026, 11, 5, 9, tzinfo=timezone.utc)

def scored(i, home, hid, away, aid, score=(2, 1), kickoff='2026-10-22T18:00:00Z'):
    return {'id': i, 'utcDate': kickoff, 'status': 'FINISHED',
            'homeTeam': {'id': hid, 'name': home, 'shortName': home},
            'awayTeam': {'id': aid, 'name': away, 'shortName': away},
            'score': {'fullTime': {'home': score[0], 'away': score[1]}}}

def odds_fixture(home='Real Sociedad', away='Lyon'):
    return {'id': 'odds:trial1234', 'utcDate': '2026-11-05T20:00:00Z', 'status': 'SCHEDULED',
            'homeTeam': {'id': 'odds-home:trial1234', 'name': home, 'shortName': home},
            'awayTeam': {'id': 'odds-away:trial1234', 'name': away, 'shortName': away},
            'score': {'fullTime': {'home': None, 'away': None}}}

def matching(a, b):
    return 1.0 if a.casefold() == b.casefold() else 0.1

class FormBridgeV27(unittest.TestCase):
    def test_verified_domestic_results_support_european_fixture(self):
        records=[]
        for k in range(8):
            records.append(scored(100+k, 'Real Sociedad de Fútbol', 101, f'TeamX{k}', 200+k))
            records.append(scored(300+k, 'Olympique Lyonnais', 102, f'TeamY{k}', 300+k))
        f=odds_fixture()
        merged,stats=bridge([f],records,NOW,matching)
        self.assertEqual(f['homeTeam']['id'],101)
        self.assertEqual(f['awayTeam']['id'],102)
        self.assertEqual(stats['oddsFixturesWithBothTeamsMatched'],1)
        self.assertEqual(stats['historyFixturesAvailable'],16)
        self.assertEqual(len(merged),17)
    def test_ambiguous_club_names_do_not_merge(self):
        records=[]
        for k in range(4):
            records.append(scored(1+k,'United',100,f'TeamX{k}',300+k))
            records.append(scored(11+k,'United',200,f'TeamY{k}',400+k))
        f=odds_fixture(home='United',away='Unknown')
        _,stats=bridge([f],records,NOW,matching)
        self.assertTrue(str(f['homeTeam']['id']).startswith('odds-home:'))
        self.assertEqual(stats['matchedOddsTeams'],0)
    def test_invalid_and_future_scores_are_not_history(self):
        good=scored(1,'A',1,'B',2)
        bad=scored(2,'A',1,'B',2,score=(None,2))
        future=scored(3,'A',1,'B',2,kickoff='2026-11-06T00:00:00Z')
        self.assertTrue(valid_finished(good,NOW))
        self.assertFalse(valid_finished(bad,NOW))
        self.assertFalse(valid_finished(future,NOW))
    def test_unavailable_provider_competition_degrades_safely(self):
        calls=[]
        def fake(url):
            calls.append(url)
            if '/PL/' in url: return {'matches':[scored(5,'A',1,'B',2)]}
            raise OSError('Data unavailable')
        matches,issues=load_free_history(fake,'https://example.org/v4',date(2026,11,5),leagues=['PL','ELC'])
        self.assertEqual(len(matches),1)
        self.assertEqual(len(issues),1)
        self.assertIn('status=FINISHED',calls[0])
    def test_incomplete_games_cannot_mint_recommendations(self):
        f=odds_fixture()
        _,stats=bridge([f],[],NOW,matching)
        self.assertEqual(stats['oddsFixturesWithBothTeamsMatched'],0)
        self.assertEqual(f['homeTeam']['id'],'odds-home:trial1234')

if __name__ == '__main__':
    unittest.main()
