'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const {familyFor,quoteIsFresh,extractMarketItems,sameFixture}=require(path.join(root,'site/market-radar-v39.js'));
const now=new Date('2026-11-06T14:00:00Z');
const at='2026-11-06T19:30:00Z';
const quoted='2026-11-06T13:00:00Z';
const q=(price,books=4)=>({price,books,lastUpdated:quoted,source:'The Odds API · median'});
const matches=[
 {id:'44',home:'HSV',away:"M'gladbach",league:'Bundesliga',kickoff:at,odds:{O25:q(1.85),U25:q(1.93)}},
 {id:'45',home:'Sevilla FC',away:'Alavés',league:'La Liga',kickoff:at,odds:{O25:q(1.58),U25:q(2.18)}},
 {id:'46',home:'Bolton',away:'Derby',league:'Championship',kickoff:at,odds:{H:q(1.78),O35:q(2.44),U35:q(1.53)}},
 {id:'47',home:'Bolton Wanderers',away:'Derby',league:'Championship',kickoff:at,odds:{O35:q(2.41),U35:q(1.56)}},
 {id:'48',home:'Arsenal',away:'Chelsea',league:'Premier League',kickoff:'2026-11-07T19:30:00Z',odds:{O25:q(1.9)}}
];
const item=(market,marketType,price,matchId='44')=>({matchId,market,marketType,
 home:matches.find(x=>x.id===matchId).home,away:matches.find(x=>x.id===matchId).away,
 label:market,price,bookmakers:4,oddsUpdatedAt:quoted,source:'The Odds API',verified:false});
const data={editionDate:'2026-11-06',matches,recommendations:[],observations:[],additionalMarkets:{tips:[],watchlist:[
 item('BTTS','btts',1.77),item('COO95','corners',1.99),item('CAO35','cards',1.77),
 {...item('GS:player','goalscorer',3.6),needsLineup:true},
 item('H1O05','first_half',1.52),item('THO15','team_goals',2.13),
 item('O25','goals',1.85),item('O25','goals',1.9,'48')
]}};
const items=extractMarketItems(data,now);
const families=new Set(items.map(x=>x.family));
assert.ok(families.size>=2,'multiple quote families represented across fixtures');
assert.ok(!items.some(x=>x.matchId==='48'),'no next-day quotes');
assert.ok(items.every(x=>x.tier==='watch'),'bookmaker odds never become recommendations');
assert.ok(items.every(x=>!['H','B','U'].includes(x.market)),'no 1X2 in market radar');
assert.equal(items.filter(x=>x.matchId==='44').length,1,'one market per real fixture');
assert.equal(items.filter(x=>x.market==='O35'&&x.home.startsWith('Bolton')).length,1,'same match, two provider-name forms');
assert.equal(items.filter(x=>x.matchId==='44').length,1,'one radar card per actual fixture');
assert.ok(!quoteIsFresh({price:1.9,books:1,lastUpdated:'2026-11-05T00:00:00Z'},now),'stale quotes');
assert.ok(!quoteIsFresh({price:1.9,books:0,lastUpdated:quoted},now),'no bookmaker');
assert.ok(!quoteIsFresh({price:null,books:2,lastUpdated:quoted},now),'no price');
assert.ok(sameFixture(matches[2],matches[3]));
assert.equal(familyFor('H',null),null);
assert.equal(familyFor('BTTSN',null),'btts');
const old={...data,editionDate:'2026-11-05'};
assert.equal(extractMarketItems(old,now).length,0,'old edition hidden');
const onlyDay={...data,additionalMarkets:{tips:[],watchlist:[]},recommendations:[
 {...item('BTTS','btts',1.9),conservativeEdge:.04,category:'safe'},
 {...item('CAO35','cards',1.9),conservativeEdge:-.1,category:'standard'}]};
const result=extractMarketItems(onlyDay,now);
assert.ok(result.every(x=>['qualified','watch'].includes(x.tier)),'only backend may qualify');
assert.ok(!result.some(x=>x.market==='CAO35'),'unqualified special picks not added to the radar as qualified');
// v40 removes independent Safe/High tips generation from the browser.
const js=fs.readFileSync(path.join(root,'site/three-fields-v26.js'),'utf8');
assert.doesNotMatch(js,/function safeMarketCandidates\(/);
assert.match(js,/OddsVisibleV40\?\.selectEdition/);
const html=fs.readFileSync(path.join(root,'site/index.html'),'utf8');
assert.match(html,/market-radar-v39\.js\?v=\d+/);assert.match(html,/market-radar-v39\.css\?v=39/);
console.log('PASS v39: safe totals, source-only radar, 7 families, time+odds+date checks, dedup, no invented tips');
