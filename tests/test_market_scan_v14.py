"""Offline regression tests for v1.4; no requests to real betting APIs."""
import unittest
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
import market_scan_v14 as m

NOW=datetime(2026,11,4,8,20,tzinfo=timezone.utc)
STAMP=NOW.isoformat()


def bookmaker(name='book1'):
    return {'key':name,'markets':[
        {'key':'alternate_totals_corners','last_update':STAMP,'outcomes':[
            {'name':'Over','point':9.5,'price':1.85},
            {'name':'Under','point':9.5,'price':1.95},
            {'name':'Over','point':8.5,'price':1.55},
        ]},
        {'key':'alternate_totals_cards','last_update':STAMP,'outcomes':[
            {'name':'Over','point':3.5,'price':1.9},
            {'name':'Under','point':3.5,'price':2.05},
        ]},
    ]}


def snapshot():
    kickoff=NOW+timedelta(hours=12)
    return {'generatedAt':STAMP,'matches':[
        {'id':'112233','status':'SCHEDULED','kickoff':kickoff.isoformat(),
         'home':'Liverpool','away':'Brentford','league':'Premier League',
         'leagueCode':'PL', 'odds':{'O25':{'price':1.75},'THO15':{'price':1.6},'H1O05':{'price':1.50},'BTTS':{'price':1.92}},
         'model':{'probabilities':{'CO85':.65,'CO95':.54}}}
    ],'recommendations':[],'safeBets':[],'highRisk':[]}


class ExtraMarketTests(unittest.TestCase):
    def test_under_and_over_corners_and_cards_have_distinct_identities(self):
        quotes=m.bookmaker_quotes({'bookmakers':[bookmaker('a'),bookmaker('b')]},
                                  {'alternate_totals_corners','alternate_totals_cards'},NOW)
        self.assertEqual(set(quotes),{'COO95','COU95','COO85','CAO35','CAU35'})
        self.assertEqual(quotes['COU95']['books'],2)
        self.assertAlmostEqual(quotes['CAO35']['price'],1.9)

    def test_undated_and_wrong_lines_never_used(self):
        malformed={'bookmakers':[{'key':'b','markets':[{
            'key':'alternate_totals_cards','last_update':STAMP,
            'outcomes':[{'name':'Over','point':3.0,'price':2},
                        {'name':'Cards','point':3.5,'price':2},
                        {'name':'Over','point':3.5,'price':-1}]}]}]}
        self.assertEqual(m.bookmaker_quotes(malformed,{'alternate_totals_cards'},NOW),{})

    def test_old_quote_is_not_used(self):
        old={'bookmakers':[{'key':'b','markets':[{'key':'alternate_totals_corners',
           'last_update':(NOW-timedelta(hours=20)).isoformat(),
           'outcomes':[{'name':'Over','point':9.5,'price':2.0}]}]}]}
        self.assertEqual(m.bookmaker_quotes(old,{'alternate_totals_corners'},NOW),{})

    def test_no_api_key_means_zero_network_and_no_fake_tips(self):
        data=snapshot()
        with patch.object(m,'get_json',side_effect=AssertionError('network')):
            result=m.run(data,'','',NOW)
        self.assertEqual(result['additionalMarkets']['tips'],[])
        self.assertEqual(result['additionalMarkets']['watchlist'],[])
        self.assertEqual(result['additionalMarkets']['providerRequests'],0)
        self.assertGreater(result['additionalMarkets']['coverage']['Mål'],0)
        self.assertGreater(result['additionalMarkets']['coverage']['Lagmål'],0)
        self.assertGreater(result['additionalMarkets']['coverage']['1. omgang'],0)

    def test_missing_stats_gives_watch_not_tip(self):
        snap=snapshot()
        event={'id':'odds-match','home_team':'Liverpool','away_team':'Brentford',
               'commence_time':snap['matches'][0]['kickoff'],
               'sport_key':'soccer_epl'}
        def provider(url,headers=None):
            if url.endswith('/events?apiKey=KEY'):return [event],None
            if 'markets=alternate_totals_corners' in url:return {'bookmakers':[bookmaker('a'),bookmaker('b')]},250
            if 'player_goal_scorer_anytime' in url:return {'bookmakers':[]},248
            if 'markets=team_totals' in url:return {'bookmakers':[]},249
            raise AssertionError('unexpected '+url)
        with patch.object(m,'get_json',side_effect=provider),\
             patch.object(m,'load_history_for_fixture',return_value=([],[])):
            result=m.run(snap,'KEY','',NOW)
        # Corner model exists for two lines, card history doesn't.
        self.assertFalse(any(p['marketType']=='cards' for p in result['additionalMarkets']['tips']))
        self.assertTrue(any(p['marketType']=='cards' for p in result['additionalMarkets']['watchlist']))
        self.assertTrue(any(p['marketType']=='corners' for p in result['additionalMarkets']['watchlist']+result['additionalMarkets']['tips']))

    def test_team_under_btts_no_and_first_half_are_distinct(self):
        event={'home_team':'Liverpool','away_team':'Brentford','bookmakers':[{ 'key':'one',
            'markets':[{'key':'team_totals','last_update':STAMP,'outcomes':[
                {'name':'Under','description':'Liverpool','point':1.5,'price':2.4},
                {'name':'Over','description':'Brentford','point':0.5,'price':1.9},
                {'name':'Over','description':'Some other team','point':1.5,'price':1.7}]},
                {'key':'btts','last_update':STAMP,'outcomes':[{'name':'No','price':1.9}]},
                {'key':'totals_h1','last_update':STAMP,'outcomes':[
                    {'name':'Under','point':0.5,'price':2.4}]}]}]}
        result=m.bookmaker_quotes(event,{'team_totals','btts','totals_h1'},NOW)
        self.assertEqual(set(result),{'THU15','TAO05','BTTSN','H1U05'})
        snap=snapshot()['matches'][0]
        snap['model']['expectedGoals']=[1.9,1.1]
        snap['model']['probabilities'].update({'BTTS':.52,'H1O05':.62})
        extra=m.watch_special_goal_markets(snap,{'bookmakers':event['bookmakers']*2},NOW)
        self.assertTrue(all(not x['verified'] for x in extra))

    def test_evaluation_requires_both_price_and_stats(self):
        q={'price':1.8,'books':2,'lastUpdated':STAMP}
        self.assertFalse(m.evaluate(q,None,'cards',10,NOW))
        self.assertFalse(m.evaluate(q,.62,'cards',7,NOW))
        self.assertTrue(m.evaluate(q,.60,'cards',9,NOW))
        self.assertFalse(m.evaluate(q,.93,'cards',9,NOW))
        self.assertFalse(m.evaluate({'price':1.8,'books':1,'lastUpdated':STAMP},.60,'cards',9,NOW))

    def test_player_identity_and_no_guessed_player(self):
        self.assertEqual(m.quote_market('player_goal_scorer_anytime',{'name':'Yes','description':'Mohamed Salah'},{}),'GS:mohamed-salah')
        self.assertIsNone(m.quote_market('player_goal_scorer_anytime',{'name':'No','description':'Mohamed Salah'},{}))
        self.assertIsNone(m.quote_market('player_goal_scorer_anytime',{'name':'Yes'},{}))

    def test_stats_history_requires_observed_values(self):
        data=[{'status':'FINISHED','utcDate':STAMP,'homeTeam':{'id':1,'statistics':{'corner_kicks':4,'yellow_cards':2}},
               'awayTeam':{'id':2,'statistics':{'corner_kicks':5,'yellow_cards':3}}},
              {'status':'FINISHED','utcDate':STAMP,'homeTeam':{'id':1},'awayTeam':{'id':3}}]
        self.assertEqual(m.statistics_rows(data,1)[0],{'corners':9,'cards':5})
        self.assertEqual(len(m.statistics_rows(data,1)),1)
        self.assertEqual(m.observed_probability([{'corners':9}]*7,[{'corners':9}]*10,'corners',8.5,'over'),(None,0))

    def test_existing_goal_team_first_half_markets_are_watched_with_real_odds(self):
        snap=snapshot()
        for q in snap['matches'][0]['odds'].values():
            q.update({'books':3,'lastUpdated':STAMP})
        with patch.object(m,'get_json',side_effect=AssertionError('No extra calls')):
            result=m.run(snap,'','',NOW)
        markets={p['marketType'] for p in result['additionalMarkets']['watchlist']}
        self.assertTrue({'goals','team_goals','first_half','btts'}.issubset(markets))

    def test_main_selection_stays_untouched(self):
        d=snapshot();d['recommendations']=[{'market':'H','price':1.6,'matchId':'112233'}]
        before=list(d['recommendations'])
        with patch.object(m,'get_json',return_value=([],None)):
            result=m.run(d,'KEY','',NOW)
        self.assertEqual(result['recommendations'],before)


if __name__=='__main__':unittest.main()
