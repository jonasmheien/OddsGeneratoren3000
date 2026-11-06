"""Integration of history evidence into today.json without touching betting thresholds."""
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_data import build_snapshot, recent_team_form

NOW=datetime(2026,11,6,13,0,tzinfo=timezone.utc)

def base_fixture(i,when,hid,aid,home,away,score=None,status='FINISHED'):
    return {'id':i,'utcDate':when.isoformat(),'status':status,
            'homeTeam':{'id':hid,'name':home,'shortName':home},
            'awayTeam':{'id':aid,'name':away,'shortName':away},
            'score':{'fullTime':{'home':score[0] if score else None,'away':score[1] if score else None}},
            'competition':{'code':'PL','name':'Premier League'}}

class FormPipelineV38(unittest.TestCase):
    def test_snapshot_and_model_use_same_historical_matches(self):
        future=base_fixture(901,NOW+timedelta(hours=6),1,2,'Liverpool','Chelsea',status='SCHEDULED')
        history=[]
        for n in range(1,8):
            history.append(base_fixture(200+n,NOW-timedelta(days=n),1,100+n,
                        'Liverpool',f'Opponent {n}',(n%3+1,n%2)))
            history.append(base_fixture(400+n,NOW-timedelta(days=n),200+n,2,
                        f'Away opponent {n}','Chelsea',(n%2,n%3+1)))
        snap=build_snapshot(NOW,[future,*history],None,[],[],{'fixtures':'ok','odds':'ok'})
        m=next(x for x in snap['matches'] if x['id']=='901')
        self.assertEqual(len(m['formMatchesHome']),5)
        self.assertEqual(len(m['formMatchesAway']),5)
        self.assertEqual(len(set(x['matchId'] for x in m['formMatchesHome'])),5)
        self.assertEqual(m['formMatchesHome'][0]['opponent'],'Opponent 1')
        self.assertEqual(m['formMatchesAway'][0]['venueLabel'],'Borte')
        self.assertEqual(m['formHome'][:5],''.join(x['resultForAnalyzedTeam'] for x in m['formMatchesHome']))
        self.assertEqual(m['formAway'][:5],''.join(x['resultForAnalyzedTeam'] for x in m['formMatchesAway']))
        self.assertEqual(m['model']['sample'],[7,7])
    def test_ambiguous_legacy_without_names_does_not_claim_display_verified(self):
        future=base_fixture(900,NOW+timedelta(hours=6),1,2,'L','C',status='SCHEDULED')
        history=[]
        for n in range(1,4):
            row=base_fixture(100+n,NOW-timedelta(days=n),1,2,'L','C',(1,1))
            row['homeTeam'].pop('name');row['homeTeam'].pop('shortName')
            history.append(row)
        snap=build_snapshot(NOW,[future,*history],None,[],[],{'fixtures':'ok','odds':'ok'})
        m=snap['matches'][0]
        self.assertEqual(m['formMatchesHome'],[])
        self.assertEqual(m['formHistoryDiagnostics']['home']['verified'],3)
        self.assertEqual(m['formHistoryDiagnostics']['home']['displayable'],0)

if __name__=='__main__':unittest.main()
