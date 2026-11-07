"""Regression: overlapping real fixtures are unique across all odds providers.
Synthetic tests, no external API, dates intentionally frozen to 2026-11-07.
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from final_selection_v40 import fixture_key, finalize, validate

NOW=datetime(2026,11,7,8,25,tzinfo=timezone.utc)
KO='2026-11-07T15:00:00Z'
STAMP='2026-11-07T08:20:00Z'
PAIRS=[
    (('Stuttgart','Bremen'),('VfB Stuttgart','Werder Bremen')),
    (('Preston NE','Southampton'),('Preston North End','Southampton')),
    (('Blackburn','West Ham'),('Blackburn Rovers','West Ham United')),
    (('Mainz','Bayern'),('FSV Mainz 05','Bayern Munich')),
    (('QPR','Lincoln City'),('Queens Park Rangers','Lincoln City')),
    (('Wrexham','Wolverhampton'),('Wrexham AFC','Wolverhampton Wanderers')),
]

def match(mid,names):
    return {'id':mid,'home':names[0],'away':names[1],
            'kickoff':KO,'league':'Testliga','status':'SCHEDULED',
            'model':None,
            'odds':{'O25':{'price':1.55,'books':5,'lastUpdated':STAMP},
                    'U25':{'price':2.45,'books':5,'lastUpdated':STAMP}}}

class FixtureIdentityV41(unittest.TestCase):
    def test_aliases_represent_exactly_one_match(self):
        for original,expanded in PAIRS:
            with self.subTest(original=original):
                self.assertEqual(fixture_key(match('fd',original)),fixture_key(match('odds',expanded)))

    def test_different_clubs_still_separate(self):
        self.assertNotEqual(fixture_key(match('a',('Preston NE','Southampton'))),
                            fixture_key(match('b',('Preston NE','West Ham'))))

    def test_full_daily_selection_deduplicates_six_pairs(self):
        matches=[]
        for i,(original,expanded) in enumerate(PAIRS):
            matches.extend((match(f'fd-{i}',original),match(f'odds-{i}',expanded)))
        edition={'editionDate':'2026-11-07','generatedAt':STAMP,'matches':matches,
                 'recommendations':[],'observations':[],'safeBets':[],
                 'highRisk':[],'coverage':{}}
        chosen=finalize(edition,NOW)
        all_picks=chosen['safeBets']+chosen['highRisk']+chosen['interestingObjects']
        ids=[x['fixtureKey'] for x in all_picks]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(len(ids),len(PAIRS),'exactly one chosen per real fixture across categories')
        self.assertGreaterEqual(chosen['finalSelection']['rejected'].get('same_fixture_or_correlated_outcome',0),5)
        self.assertTrue(validate(chosen))

    def test_injected_duplicate_fails_closed(self):
        one=match('fd',PAIRS[0][0]);two=match('odds',PAIRS[0][1])
        edition={'editionDate':'2026-11-07','generatedAt':STAMP,
                 'matches':[one,two],'recommendations':[],'observations':[],
                 'safeBets':[],'highRisk':[],'coverage':{}}
        chosen=finalize(edition,NOW)
        forged={**chosen['safeBets'][0], 'home':PAIRS[0][1][0], 'away':PAIRS[0][1][1],
                'matchId':'odds', 'fixtureKey':fixture_key(two),'selectionId':'fake-v41'}
        chosen['highRisk'].append(forged)
        with self.assertRaises(ValueError):validate(chosen)

if __name__=='__main__':unittest.main()
