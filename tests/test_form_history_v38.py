"""Offline invariants for real, correctly attributed match history."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'scripts'))
from form_history_v38 import verified_form_records, model_rows, source_identity_confirmed

NOW=datetime(2026,11,6,13,0,tzinfo=timezone.utc)

def game(i,when,hid=1,aid=2,h='Hjemmelag',a='Bortelag',score=(2,1),status='FINISHED',duration='REGULAR',regular=None):
    row={'id':i,'utcDate':when,'status':status,
         'homeTeam':{'id':hid,'name':h},'awayTeam':{'id':aid,'name':a},
         'competition':{'code':'PL','name':'Premier League'},
         'score':{'fullTime':{'home':score[0],'away':score[1]},'duration':duration}}
    if regular is not None:row['score']['regularTime']={'home':regular[0],'away':regular[1]}
    return row

class VerifiedFormTests(unittest.TestCase):
    def setUp(self):
        self.y=(NOW-timedelta(days=1)).isoformat()
    def test_home_wins_loss_draw_and_zero_zero(self):
        rows=[game('a',self.y,score=(2,1)),game('b',(NOW-timedelta(days=2)).isoformat(),score=(0,0)),game('c',(NOW-timedelta(days=3)).isoformat(),score=(0,2))]
        h,_=verified_form_records(rows,1,NOW)
        a,_=verified_form_records(rows,2,NOW)
        self.assertEqual(''.join(r['resultForAnalyzedTeam'] for r in h),'WDL')
        self.assertEqual(''.join(r['resultForAnalyzedTeam'] for r in a),'LDW')
        self.assertEqual(h[0]['venueLabel'],'Hjemme')
        self.assertEqual(a[0]['venueLabel'],'Borte')
        self.assertEqual((a[0]['homeGoals'],a[0]['awayGoals']),(2,1))
        self.assertEqual((a[0]['analyzedTeamGoals'],a[0]['opponentGoals']),(1,2))
        self.assertEqual([r[3] for r in model_rows(a)],['L','D','W'])
    def test_away_win_home_loss(self):
        rows=[game(12,self.y,score=(0,4))]
        a,_=verified_form_records(rows,2,NOW)
        self.assertEqual(a[0]['resultForAnalyzedTeam'],'W')
        self.assertEqual(a[0]['analyzedTeamGoals'],4)
        self.assertEqual(a[0]['opponent'],'Hjemmelag')
        h,_=verified_form_records(rows,1,NOW)
        self.assertEqual(h[0]['resultForAnalyzedTeam'],'L')
    def test_filters_not_finished_future_expired_or_wrong_team(self):
        rows=[game(1,self.y),game(2,self.y,status='IN_PLAY'),game(3,self.y,status='POSTPONED'),
              game(4,(NOW+timedelta(days=1)).isoformat()),game(5,(NOW-timedelta(days=185)).isoformat()),
              game(6,self.y,hid=3,aid=4)]
        got,_=verified_form_records(rows,1,NOW)
        self.assertEqual([r['matchId'] for r in got],['1'])
    def test_invalid_scores_never_published(self):
        rows=[game(1,self.y,score=(None,1)),game(2,self.y,score=(-1,2)),game(3,self.y,score=(True,0)),game(4,self.y)]
        got,issues=verified_form_records(rows,1,NOW)
        self.assertEqual([r['matchId'] for r in got],['4'])
        self.assertIn('invalid_score',issues)
    def test_penalty_and_extra_time_regulation_only(self):
        rows=[game('extra',self.y,score=(3,2),duration='EXTRA_TIME',regular=(1,1)),
              game('pen',(NOW-timedelta(days=2)).isoformat(),score=(5,4),duration='PENALTY_SHOOTOUT',regular=(2,2)),
              game('unknown',(NOW-timedelta(days=3)).isoformat(),score=(5,2),duration='PENALTY_SHOOTOUT')]
        got,issues=verified_form_records(rows,1,NOW)
        self.assertEqual([x['resultForAnalyzedTeam'] for x in got],['D','D'])
        self.assertIn('invalid_score',issues)
    def test_duplicate_and_conflict(self):
        row=game('same',self.y)
        valid,issues=verified_form_records([row,row],1,NOW)
        self.assertEqual(len(valid),1)
        self.assertIn('duplicate_merged',issues)
        conflict=game('same',self.y,score=(0,3))
        valid,issues=verified_form_records([row,conflict],1,NOW)
        self.assertEqual(valid,[])
        self.assertIn('score_conflict',issues)
    def test_distinct_fixtures_same_teams_remain_distinct(self):
        rows=[game(1,self.y),game(2,(NOW-timedelta(days=3)).isoformat(),score=(1,0))]
        got,_=verified_form_records(rows,1,NOW)
        self.assertEqual(len(got),2)
    def test_different_providers_same_ids_not_mixed(self):
        row=game('apf:3',self.y,hid='apf:1',aid='apf:2')
        out,_=verified_form_records([row],1,NOW)
        self.assertEqual(out,[])
        out,_=verified_form_records([row],'apf:1',NOW)
        self.assertEqual(len(out),1)
    def test_source_order_and_utc_sort(self):
        earlier=game('apf:10',(NOW-timedelta(days=4)).isoformat())
        newer=game(20,self.y)
        got,_=verified_form_records([earlier,newer],1,NOW)
        self.assertEqual([r['matchId'] for r in got],['20','apf:10'])
        self.assertEqual(got[0]['source'],'football-data.org')
    def test_same_event_conflicting_providers_rejected(self):
        a=game(13,self.y,score=(2,1));b=game('apf:13',self.y,score=(1,0))
        got,notes=verified_form_records([a,b],1,NOW)
        self.assertEqual(got,[])
        self.assertIn('score_conflict',notes)
    def test_synthetic_link_needs_confirmed_name(self):
        row=game(8,self.y,h='Bolton Wanderers',a='Derby County')
        found,_=verified_form_records([row],1,NOW)
        self.assertTrue(source_identity_confirmed(['Bolton'],found))
        self.assertFalse(source_identity_confirmed(['Bolton United'],found))
        row=game(9,self.y,h='PEC Zwolle',a='Vitesse')
        found,_=verified_form_records([row],1,NOW)
        self.assertTrue(source_identity_confirmed(['FC Zwolle'],found))
        row=game(10,self.y,h='Hamburger SV',a='Vitesse')
        found,_=verified_form_records([row],1,NOW)
        self.assertTrue(source_identity_confirmed(['HSV'],found))

    def test_missing_team_labels_are_not_fabricated(self):
        row=game(12,self.y,h='',a='')
        got,_=verified_form_records([row],1,NOW)
        self.assertEqual(len(got),1)
        self.assertFalse(got[0]['displayComplete'])
        self.assertEqual(got[0]['homeTeam']['name'],'')

if __name__=='__main__':unittest.main()
