"""Regression checks for v1.5 data, updated for the selective v1.6 presentation.

No outside web calls, no invented expert projections or official logo licenses.
"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'scripts'))
import market_scan_v14 as market

NOW = datetime(2026,11,4,8,20,tzinfo=timezone.utc)

class MarketViewV15Tests(unittest.TestCase):
    def test_all_seven_market_groups_are_explicit(self):
        source = (ROOT/'site'/'market-board-v14.js').read_text(encoding='utf-8')
        for name in ('Mål', 'Lagmål', 'Begge lag scorer', '1. omgang',
                     'Hjørnespark', 'Kort', 'Målscorer'):
            self.assertIn(name, source)
        self.assertIn('aria-pressed', source)
        self.assertIn('Ingen ekstra markeder oppfyller kvalitetskravene', source)

    def test_score_consensus_is_not_hidden_when_missing(self):
        js=(ROOT/'site'/'score-consensus-v14.js').read_text(encoding='utf-8')
        self.assertIn('Dagsutgaven er ennå ikke analysert', js)
        self.assertIn('Forebet, Vitibet, PredictZ og WinDrawWin er ikke automatisk tilkoblet', js)
        self.assertIn('rows.length>=2', js)
        self.assertNotIn('root.hidden=true', js)

    def test_logos_cannot_be_shown_by_default_without_permission(self):
        js=(ROOT/'site'/'app.js').read_text(encoding='utf-8')
        self.assertIn("licensedCrests===true", js)
        self.assertIn('badgeAccent', js)
        self.assertIn('team-monogram', js)
        self.assertIn('safeCrest(url)', js)

    def test_no_site_data_or_state_is_overwritten_by_patch(self):
        index=(ROOT/'site'/'index.html').read_text(encoding='utf-8')
        self.assertIn('market-board-v14.js?v=16', index)
        self.assertIn('score-consensus-v14.js?v=16', index)
        self.assertIn('Data provided by football-data.org', index)
        self.assertTrue((ROOT/'site'/'data'/'today.json').exists())

    def test_backend_reports_all_market_families_even_with_no_provider(self):
        snap={'generatedAt':NOW.isoformat(), 'recommendations':[],
              'safeBets':[], 'highRisk':[], 'matches':[]}
        with patch.object(market,'get_json',side_effect=AssertionError('unexpected web request')):
            result=market.run(snap,'','',NOW)
        self.assertEqual(len(result['additionalMarkets']['marketFamilies']),7)
        self.assertEqual(result['additionalMarkets']['watchlist'],[])
        self.assertEqual(result['additionalMarkets']['tips'],[])

    def test_corners_and_cards_under_are_distinct_observations(self):
        stamp=NOW.isoformat()
        event={'bookmakers':[{'key':'one','markets':[
            {'key':'alternate_totals_corners','last_update':stamp,'outcomes':[
                {'name':'Over','point':9.5,'price':1.9},{'name':'Under','point':9.5,'price':1.95}]},
            {'key':'alternate_totals_cards','last_update':stamp,'outcomes':[
                {'name':'Over','point':3.5,'price':1.8},{'name':'Under','point':3.5,'price':2.05}]}]}]}
        quote=market.bookmaker_quotes(event,{'alternate_totals_corners','alternate_totals_cards'},NOW)
        self.assertEqual(set(quote),{'COO95','COU95','CAO35','CAU35'})

if __name__=='__main__':unittest.main()
