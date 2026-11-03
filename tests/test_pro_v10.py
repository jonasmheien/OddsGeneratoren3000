"""Source-traceability, brand-asset gating and archived result regression tests."""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import lifecycle
import build_data

ROOT=Path(__file__).resolve().parents[1]

class ProV10Tests(unittest.TestCase):
    def test_official_crest_urls_are_metadata_not_an_unlicensed_public_image(self):
        now=datetime(2026,11,4,8,17,tzinfo=timezone.utc)
        fixture={'id':101,'status':'SCHEDULED','utcDate':(now+timedelta(hours=10)).isoformat(),
                 'homeTeam':{'id':1,'name':'Home Club','crest':'https://crests.football-data.org/1.svg'},
                 'awayTeam':{'id':2,'name':'Away Club','crest':'https://crests.football-data.org/2.png'},
                 'competition':{'name':'League','code':'PL','emblem':'https://crests.football-data.org/PL.png'}}
        with patch.dict(os.environ,{},clear=True):
            result=build_data.build_snapshot(now,[fixture],None,[],[],{'fixtures':'ok','odds':'not_configured'})
        self.assertFalse(result['visualAssets']['licensedCrests'])
        m=result['matches'][0]
        self.assertEqual(m['homeCrest'],fixture['homeTeam']['crest'])
        self.assertEqual(m['leagueCrest'],fixture['competition']['emblem'])
        with patch.dict(os.environ,{'SHOW_LICENSED_CRESTS':'1'}):
            enabled=build_data.build_snapshot(now,[fixture],None,[],[],{'fixtures':'ok','odds':'not_configured'})
        self.assertTrue(enabled['visualAssets']['licensedCrests'])

    def test_history_deduplicates_repeated_pick_and_only_includes_settled(self):
        base={'editionDate':'2026-11-04','recommendations':[], 'safeBets':[], 'highRisk':[]}
        settled={'matchId':'101','market':'H','price':1.6,'result':{'status':'won'}}
        lost={'matchId':'102','market':'O25','price':2.2,'result':{'status':'lost'}}
        live={'matchId':'103','market':'B','result':{'status':'live'}}
        base['recommendations']=[settled,live]
        base['safeBets']=[settled]
        base['highRisk']=[lost]
        with patch.object(lifecycle,'HISTORY',ROOT/'tests'/'archive-does-not-exist'):
            history=lifecycle.published_history(base)
        self.assertEqual(len(history),1)
        self.assertEqual(len(history[0]['picks']),2)
        self.assertEqual({p['status'] for p in history[0]['picks']},{'won','lost'})

    def test_history_hides_unsettled_and_preserves_price(self):
        base={'editionDate':'2026-11-04','recommendations':[
          {'matchId':'101','market':'O25','price':2.31,'result':{'status':'won'}},
          {'matchId':'102','market':'H','price':1.70,'result':{'status':'unverified'}}],
          'safeBets':[], 'highRisk':[]}
        with patch.object(lifecycle,'HISTORY',ROOT/'tests'/'archive-does-not-exist'):
            result=lifecycle.published_history(base)
        self.assertEqual(result[0]['picks'],[{'status':'won','matchId':'101','market':'O25','price':2.31}])

    def test_public_brand_logo_is_original_local_vector(self):
        html=(ROOT/'site/index.html').read_text()
        mark=(ROOT/'site/assets/og-mark.svg').read_text()
        js=(ROOT/'site/app.js').read_text()
        self.assertIn('assets/og-mark.svg',html)
        self.assertIn('viewBox="0 0 80 80"',mark)
        self.assertIn('canUseCrests',js)
        self.assertIn('crests.football-data.org',js)
        self.assertIn('id="resultater"',html)
        self.assertNotIn('Dekning begrenset',html)
        self.assertNotIn('Data og statistikk',html)

if __name__=='__main__':unittest.main()
