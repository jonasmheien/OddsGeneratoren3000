import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from final_selection_v40 import finalize, validate, fixture_key, market_identity, market_label

AT='2026-11-06T15:00:00+00:00'
KO='2026-11-06T19:30:00+00:00'
NOW=datetime.fromisoformat(AT)

def quote(price,books=5):return {'price':price,'books':books,'lastUpdated':AT,'source':'Fixture quotes'}

def game(mid,home,away,odds=None):
    return {'id':mid,'home':home,'away':away,'league':'Test','kickoff':KO,'status':'SCHEDULED',
            'odds':odds or {},'model':None}

def snap(matches, recommendations=None,observations=None):
    return {'editionDate':'2026-11-06','generatedAt':AT,'matches':matches,
            'recommendations':recommendations or [],'observations':observations or [],
            'safeBets':[],'highRisk':[],'coverage':{}}

class FinalSelectionTests(unittest.TestCase):
    def test_market_scope(self):
        self.assertEqual(market_identity('O25')['line'],2.5)
        self.assertEqual(market_identity('U25')['outcome'],'under')
        self.assertEqual(market_identity('H1O15')['period'],'first_half')
        self.assertEqual(market_identity('COU95')['family'],'corners')
        self.assertEqual(market_identity('CAO35')['family'],'cards')
        self.assertEqual(market_identity('THO15')['subject'],'home')
        self.assertEqual(market_identity('TAU15')['subject'],'away')
        self.assertEqual(market_identity('BTTSN')['outcome'],'no')
        self.assertEqual(market_identity('GS:shuto-machino')['subject'],'shuto-machino')
        self.assertIsNone(market_identity('H1015'))
        self.assertEqual(market_label('H1O15'),'1. omgang over 1,5 mål')
        self.assertEqual(market_label('COO95'),'Over 9,5 hjørnespark')
    def test_provider_alias_and_opposing_totals(self):
        m=[game('fd','HSV',"M'gladbach",{'O25':quote(1.5),'U25':quote(2.55)}),
           game('odds','Hamburger SV','Borussia Monchengladbach',{'O25':quote(1.5),'U25':quote(2.55)})]
        self.assertEqual(fixture_key(m[0]),fixture_key(m[1]))
        a=finalize(snap(m),NOW)
        actual=a['safeBets']+a['highRisk']+a['interestingObjects']
        self.assertEqual(len(actual),1)
        self.assertEqual(actual[0]['market'],'O25')
        self.assertTrue(validate(a))
    def test_conflicts_across_categories_and_recommendations(self):
        m=game('a','Home','Away',{'O25':quote(1.5),'U25':quote(2.55),
                                  'H':quote(2.50),'U':quote(3.55),'B':quote(2.90)})
        qualified={'matchId':'a','home':'Home','away':'Away','kickoff':KO,'market':'U25',
                   'label':'Under 2,5 mål','price':2.55,'bookmakers':5,'oddsUpdatedAt':AT,
                   'category':'high','conservativeEdge':.06}
        a=finalize(snap([m],recommendations=[qualified]),NOW)
        self.assertEqual([x['market'] for x in a['highRisk']],['U25'])
        self.assertEqual(a['safeBets'],[])
        self.assertEqual(a['recommendations'][0]['selectionId'],a['highRisk'][0]['selectionId'])
        self.assertGreater(a['finalSelection']['rejected']['same_fixture_or_correlated_outcome'],0)
    def test_mutual_exclusive_result_and_btts(self):
        m=game('a','Home','Away',{'H':quote(1.50),'U':quote(4.0),'B':quote(8.0)})
        obs=[{'matchId':'a','home':'Home','away':'Away','kickoff':KO,'market':'BTTS',
              'label':'Begge lag scorer: Ja','price':1.9,'bookmakers':5,
              'oddsUpdatedAt':AT,'probability':.63}]
        a=finalize(snap([m],observations=obs),NOW)
        self.assertEqual(sum(len(a[k]) for k in ('safeBets','highRisk','interestingObjects')),1)
        self.assertEqual(a['safeBets'][0]['market'],'H')
    def test_different_fixtures_stay_eligible(self):
        a=finalize(snap([game('a','Lyn','Brann',{'O25':quote(1.5),'U25':quote(2.55)}),
                         game('b','Viking','Molde',{'O25':quote(1.5),'U25':quote(2.55)}),
                         game('c','Bodo','Tromso',{'O25':quote(1.5),'U25':quote(2.55)})]),NOW)
        self.assertEqual(len(a['safeBets']),3)
        self.assertIsNone(a['finalSelection']['shortfalls']['safe'])
        self.assertIsNotNone(a['finalSelection']['shortfalls']['high'])
    def test_one_fixture_in_same_family_alternate_lines(self):
        m=game('z','Roma','Lazio',{'O25':quote(1.5),'U25':quote(2.55),
                                  'O15':quote(1.22),'U15':quote(5.0)})
        a=finalize(snap([m]),NOW)
        self.assertEqual(len(a['safeBets']),1)
        self.assertIn(a['safeBets'][0]['market'],('O15','O25'))
    def test_backend_fails_on_injected_conflict(self):
        m=[game('a','HSV',"M'gladbach",{'O25':quote(1.5),'U25':quote(2.55)}),
           game('b','Brann','Lyn',{'O25':quote(1.5),'U25':quote(2.55)})]
        a=finalize(snap(m),NOW)
        a['highRisk'].append({**a['safeBets'][0], 'market':'U25'})
        with self.assertRaises(ValueError):validate(a)
    def test_past_fixture_not_selected(self):
        m=game('x','Home','Away',{'O25':quote(1.5),'U25':quote(2.55)})
        m['kickoff']='2026-11-06T12:00:00+00:00'
        a=finalize(snap([m]),NOW)
        self.assertEqual(a['safeBets'],[])

if __name__=='__main__':unittest.main()
