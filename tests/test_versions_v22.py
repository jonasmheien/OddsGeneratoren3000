from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from versions_v22 import compare_editions, publish_version_history, record_revision


def pick(match='42', market='H', price=1.8):
    return {'matchId':match,'market':market,'price':price,'home':'A','away':'B','label':'Hjemmeseier'}


class RevisionTests(unittest.TestCase):
    def test_reason_does_not_claim_loss_of_value(self):
        before={'recommendations':[pick()]}
        after={'recommendations':[pick('43')]}
        diff=compare_editions(before,after)
        self.assertEqual(len(diff['removed']),1)
        self.assertNotIn('mistet verdi',diff['removed'][0]['reason'])
        self.assertEqual(len(diff['added']),1)

    def test_price_changes(self):
        diff=compare_editions({'recommendations':[pick()]}, {'recommendations':[pick(price=2.1)]})
        self.assertEqual(diff['repriced'][0]['oldPrice'],1.8)
        self.assertEqual(diff['repriced'][0]['newPrice'],2.1)

    def test_archived_snapshot_and_public_index(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            old={'editionDate':'2026-11-04','generatedAt':'2026-11-04T09:17:00+00:00','recommendations':[pick()]}
            new={'localDate':'2026-11-04','generatedAt':'2026-11-04T15:17:00+00:00','recommendations':[]}
            path=record_revision(old,new,root)
            self.assertTrue(path.exists())
            self.assertEqual(len(json.loads(path.read_text())['previousEdition']['recommendations']),1)
            self.assertEqual(record_revision(old,new,root),path)
            self.assertEqual(len(publish_version_history(root)),1)
            self.assertTrue((root/'site/data/versions.json').exists())

    def test_no_cross_date_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            old={'editionDate':'2026-11-03','generatedAt':'old','recommendations':[pick()]}
            new={'localDate':'2026-11-04','generatedAt':'new','recommendations':[]}
            self.assertIsNone(record_revision(old,new,Path(folder)))


if __name__=='__main__':unittest.main()
