"""Offline regression tests: no API, credentials or mutable betting results."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from quality_monitor_v42 import quality_report, performance_report, prune_preview, publish

NOW = datetime(2026, 11, 9, 11, 0, tzinfo=timezone.utc)

class MonitorV42(unittest.TestCase):
    def test_data_coverage_and_provenance_are_explicit(self):
        edition = {'editionDate':'2026-11-09','generatedAt':'2026-11-09T09:00:00Z',
            'coverage':{'upcomingMatches':7,'matchedOdds':3,'withModel':6,'qualified':0},
            'dataStatus':{'officialFormBridge':{'oddsFixturesWithBothTeamsMatched':0},'externalPredictionsCount':0},
            'safeBets':[{'market':'H'}],'highRisk':[],'interestingObjects':[]}
        out = quality_report(edition,NOW)
        self.assertEqual(out['data']['oddsCoveragePct'],42.9)
        self.assertEqual(out['data']['safeBets'],1)
        self.assertEqual(out['data']['qualifiedRecommendations'],0)
        self.assertGreaterEqual(len(out['issues']),2)
        self.assertEqual(out['freshness'],'current')

    def test_unpublished_today_is_a_warning_not_a_fake_edition(self):
        out = quality_report({'editionDate':'2026-11-08'},NOW)
        self.assertEqual(out['freshness'],'not_published')
        self.assertTrue(any('Ingen dagsutgave' in issue for issue in out['issues']))

    def test_historical_roi_and_dedup(self):
        data=[{'date':'2026-11-08','picks':[
            {'matchId':1,'market':'H','price':2.4,'status':'won'},
            {'matchId':1,'market':'H','price':2.4,'status':'won'},
            {'matchId':2,'market':'B','price':1.7,'status':'lost'},
            {'matchId':3,'market':'O25','status':'void'},
            {'matchId':4,'market':'B','price':9,'status':'unverified'}]}]
        out=performance_report(data,NOW)
        self.assertEqual(out['sample'],{'settled':3,'wins':1,'losses':1,'voids':1})
        self.assertEqual(out['flatStake']['profitUnits'],.4)
        self.assertEqual(out['flatStake']['roiPct'],20.0)
        self.assertTrue(out['insufficientSample'])
        self.assertFalse(out['closingLineValue']['available'])
        self.assertFalse(out['calibration']['available'])

    def test_invalid_odds_do_not_corrupt_roi(self):
        out=performance_report([{'date':'2026-11-08','picks':[
            {'matchId':1,'market':'B','price':'NaN','status':'won'},
            {'matchId':2,'market':'H','price':None,'status':'lost'},
            {'matchId':3,'market':'B','price':9,'status':'void'}]}],NOW)
        self.assertEqual(out['sample']['settled'],1)
        self.assertIsNone(out['flatStake']['roiPct'])

    def test_stale_preview_pruned_future_kept(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'tomorrow.json'
            path.write_text(json.dumps({'previewEdition':True,'editionDate':'2026-11-07'}))
            self.assertTrue(prune_preview(path,{'editionDate':'2026-11-08'},NOW))
            self.assertFalse(path.exists())
            path.write_text(json.dumps({'previewEdition':True,'editionDate':'2026-11-10'}))
            self.assertFalse(prune_preview(path,{'editionDate':'2026-11-09'},NOW))
            self.assertTrue(path.exists())

    def test_publish_never_edits_active_picks_or_history(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'site/data';path.mkdir(parents=True)
            obj={'editionDate':'2026-11-09','generatedAt':NOW.isoformat(),
                'safeBets':[{'market':'H','price':2.1}]}
            (path/'today.json').write_text(json.dumps(obj))
            (path/'history.json').write_text('[]')
            publish(t,NOW)
            self.assertEqual(json.loads((path/'today.json').read_text()),obj)
            self.assertTrue((path/'quality-v42.json').is_file())
            self.assertTrue((path/'performance-v42.json').is_file())

if __name__=='__main__':unittest.main()
