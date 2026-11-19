"""One immutable published selection per fixture across refreshes and history."""
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import hitrate_v51
import lifecycle
from final_selection_v40 import finalize
from publication_policy_v53 import fixture_identity, publication_locks, lock_edition
from tomorrow_v24 import publish_preview

NOW = datetime(2026, 11, 17, 9, tzinfo=timezone.utc)
KO = '2026-11-17T19:45:00Z'


def pick(market='B', mid='odds:first'):
    return dict(matchId=mid, home='Denmark', away='Norway', league='UEFA Nations League',
                kickoff=KO, market=market, label={'B': 'Borteseier', 'H': 'Hjemmeseier'}[market], price=2.9)


def journal(root, alternatives=False):
    path = root / 'state/tip-audit-v34/2026-11-17.json'
    path.parent.mkdir(parents=True)
    revisions = [dict(id='first', recordedAt='2026-11-16T21:00:00Z', groups={'high': [pick()]})]
    if alternatives:
        revisions.append(dict(id='second', recordedAt='2026-11-17T08:00:00Z',
                              groups={'high': [pick('H', 'new-provider-id')]}))
    path.write_text(json.dumps(dict(schemaVersion=34, editionDate='2026-11-17', revisions=revisions)))
    return path


def snapshot(at=NOW):
    odds = {code: dict(price=price, books=7, lastUpdated=at.isoformat())
            for code, price in [('H', 2.3), ('U', 3.3), ('B', 2.9)]}
    return dict(localDate='2026-11-17', editionDate='2026-11-17', generatedAt=at.isoformat(),
                dataStatus={'fixtures': 'ok', 'odds': 'ok'}, coverage={'upcomingMatches': 1, 'matchedOdds': 1},
                matches=[dict(id='new-provider-id', home='Denmark', away='Norway', kickoff=KO,
                              league='UEFA Nations League', status='SCHEDULED', odds=odds)],
                recommendations=[], observations=[])


class FirstPublicationTests(unittest.TestCase):
    def test_refresh_keeps_first_market_across_providers_and_categories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal(root)
            locks = publication_locks(root, NOW)
            self.assertEqual(next(iter(locks.values()))['market'], 'B')
            self.assertEqual(finalize(snapshot(), NOW)['highRisk'][0]['market'], 'H')
            refreshed = finalize(snapshot(), NOW, publication_locks=locks)
            self.assertEqual([p['market'] for p in refreshed['highRisk']], ['B'])
            self.assertEqual(refreshed['finalSelection']['rejected']['previously_published_selection'], 1)

    def test_unavailable_locked_market_is_omitted_without_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal(root)
            candidate = snapshot()
            candidate['matches'][0]['odds']['B']['books'] = 1
            result = finalize(candidate, NOW, publication_locks=publication_locks(root, NOW))
            self.assertEqual(result['highRisk'], [])
            self.assertEqual(result['safeBets'], [])
            self.assertEqual(result['interestingObjects'], [])

    def test_daily_and_preview_publishing_both_enforce_locks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal(root)
            candidate = finalize(snapshot(), NOW)
            with patch.object(lifecycle, 'ROOT', root):
                saved = lifecycle.create_edition(candidate, None, '')
            self.assertEqual([p['market'] for p in saved['highRisk']], ['B'])
            evening = datetime(2026, 11, 16, 22, tzinfo=timezone.utc)
            candidate = finalize(snapshot(evening), evening)
            target = root / 'site/data/tomorrow.json'
            publish_preview(candidate, evening, target)
            saved = json.loads(target.read_text())
            self.assertEqual([p['market'] for p in saved['highRisk']], ['B'])

    def test_first_losing_pick_counts_and_later_winner_stays_in_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = journal(root, alternatives=True)
            original = path.read_bytes()
            after = datetime(2026, 11, 18, tzinfo=timezone.utc)
            # Home wins: first published away win loses, later home tip wins.
            row = dict(id='uefa:1', utcDate=KO, status='FINISHED', homeTeam={'name': 'Denmark'},
                       awayTeam={'name': 'Norway'}, score={'fullTime': {'home': 2, 'away': 1}},
                       resultSource='UEFA')
            hitrate_v51.sync(root, after, fetcher=lambda *_: [row])
            report = json.loads((root / 'site/data/hitrate-v51.json').read_text())
            ledger = json.loads((root / 'state/hitrate-v51.json').read_text())
            self.assertEqual(len(ledger['records']), 2)
            self.assertEqual(report['overall']['total'], 1)
            self.assertEqual(report['categories']['high']['hitRatePct'], 0)
            self.assertEqual(report['tips'][0]['market'], 'B')
            self.assertEqual(report['tips'][0]['result']['status'], 'lost')
            self.assertEqual(report['publicationPolicy']['excludedAlternatives'], 1)
            self.assertEqual(path.read_bytes(), original)
            again = hitrate_v51.sync(root, after, offline=True)
            self.assertFalse(again['changed'])

    def test_post_kickoff_or_future_journal_cannot_lock_an_unpublished_tip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = journal(root)
            data = json.loads(path.read_text())
            data['revisions'][0]['recordedAt'] = '2026-11-17T20:00:00Z'
            path.write_text(json.dumps(data))
            self.assertEqual(publication_locks(root, NOW), {})
            self.assertEqual(publication_locks(root, datetime(2026, 11, 18, tzinfo=timezone.utc)), {})

    def test_real_denmark_norway_history_contains_only_first_publication(self):
        ledger = json.loads((ROOT / 'state/hitrate-v51.json').read_text())
        report = hitrate_v51.report(ledger, NOW, {})
        danish = [p for p in report['tips'] if p['home'] == 'Denmark' and p['away'] == 'Norway']
        self.assertEqual(len(danish), 1)
        self.assertEqual(danish[0]['market'], 'B')
        identities = [fixture_identity(p) for p in report['tips']]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual(set(report['categories']), {'safe', 'high', 'watch'})


if __name__ == '__main__':
    unittest.main()
