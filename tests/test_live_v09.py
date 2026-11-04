"""End-to-end safeguards for the v0.9 live UI and result polling."""
import io
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import lifecycle

class LiveV09Tests(unittest.TestCase):
    def pick(self, market='H'):
        return {'matchId':'201', 'kickoff':'2026-11-03T21:00:00+01:00',
                'home':'A', 'away':'B', 'market':market, 'price':1.46}

    def test_minutes_and_current_score_are_displayed_only_when_provider_supplies_them(self):
        m={'id':201,'status':'IN_PLAY','minute':67,'score':{'fullTime':{'home':2,'away':1}}}
        out=lifecycle.score_pick(self.pick(),m)['result']
        self.assertEqual(out,{'status':'live','phase':'Live','minute':67,'score':{'home':2,'away':1}})
        self.assertNotIn('minute',lifecycle.score_pick(self.pick(),{'status':'IN_PLAY','score':{'fullTime':{'home':1,'away':0}}})['result'])

    def test_pause_phase_and_not_a_premature_win(self):
        m={'id':201,'status':'PAUSED','score':{'fullTime':{'home':1,'away':0}}}
        result=lifecycle.score_pick(self.pick(),m)['result']
        self.assertEqual(result['status'],'live')
        self.assertEqual(result['phase'],'Pause')

    def test_settlement_cannot_be_overwritten_by_stale_in_play(self):
        b={'localDate':'2026-11-03', 'generatedAt':'2026-11-03T08:17:00Z',
           'recommendations':[self.pick()], 'safeBets':[], 'highRisk':[]}
        b=lifecycle.with_initial_results(b)
        final={'id':201,'status':'FINISHED','score':{'fullTime':{'home':3,'away':0}}}
        b,_=lifecycle.apply_results(b,[final]);self.assertEqual(b['recommendations'][0]['result']['status'],'won')
        stale={'id':201,'status':'IN_PLAY','minute':75,'score':{'fullTime':{'home':2,'away':0}}}
        b,changed=lifecycle.apply_results(b,[stale]);self.assertFalse(changed)
        self.assertEqual(b['recommendations'][0]['result']['score'],{'home':3,'away':0})

    def test_result_fetch_uses_documented_date_range_and_filters_ids(self):
        b={'editionDate':'2026-11-03','recommendations':[self.pick()],'safeBets':[],'highRisk':[]}
        payload={'matches':[{'id':201,'status':'IN_PLAY'}, {'id':202,'status':'FINISHED'}]}
        urls=[]
        def fake_open(req,timeout=35):
            urls.append(req.full_url)
            return io.BytesIO(json.dumps(payload).encode())
        with patch.object(lifecycle,'urlopen',fake_open):
            matches=lifecycle.fetch_results(b,'fake-key')
        self.assertEqual(len(urls),1)
        self.assertEqual([m['id'] for m in matches],[201])
        query=parse_qs(urlparse(urls[0]).query)
        self.assertEqual(query['dateFrom'],['2026-11-02'])
        self.assertEqual(query['dateTo'],['2026-11-05'])
        self.assertNotIn('ids',query)

    def test_public_interface_has_no_clutter_section(self):
        html=(ROOT/'site/index.html').read_text()
        for phrase in ('Dekning begrenset','Data og statistikk','Kamper analysert','KAMPDEKNING'):
            self.assertNotIn(phrase,html)
        self.assertIn('id="live"',html)
        self.assertIn('id="top-picks"',html)
        self.assertIn('id="safe-list"',html)
        self.assertIn('id="high-list"',html)

if __name__=='__main__': unittest.main()
