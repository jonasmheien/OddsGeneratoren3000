'use strict';
// v41 UI is a defensive filter, not an independent betting recommender.
const assert=require('node:assert/strict');
const vis=require('../site/visible-selection-v40.js');
const now=new Date('2026-11-07T08:30:00Z');
const KO='2026-11-07T15:00:00Z';
function p(id,home,away){return {matchId:id,home,away,kickoff:KO,
  label:'Over 2,5 mål',market:'O25',price:1.55,category:'safe'};}
const edition={editionDate:'2026-11-07',localDate:'2026-11-07',previewEdition:true,
  finalSelection:{version:40},safeBets:[
    p('fd1','Stuttgart','Bremen'),p('odds1','VfB Stuttgart','Werder Bremen'),
    p('fd2','Preston NE','Southampton'),p('odds2','Preston North End','Southampton')],
  highRisk:[p('fd3','Blackburn','West Ham'),p('odds3','Blackburn Rovers','West Ham United'),
    p('new','Watford','Middlesbrough')],
  interestingObjects:[p('watch','Mainz','Bayern'),p('watch2','FSV Mainz 05','Bayern Munich')]};
assert.equal(vis.fixtureIdentity(edition.safeBets[0]),vis.fixtureIdentity(edition.safeBets[1]));
assert.equal(vis.fixtureIdentity(edition.safeBets[2]),vis.fixtureIdentity(edition.safeBets[3]));
let chosen=vis.selectEdition(null,edition,now);
assert.ok(chosen.authoritative);
assert.equal(chosen.groups.safe.length,2);
assert.equal(chosen.groups.high.length,2);
assert.equal(chosen.groups.watch.length,1);
const all=Object.values(chosen.groups).flat();
assert.equal(new Set(all.map(vis.fixtureIdentity)).size,all.length);
assert.ok(all.every(x=>x.price===1.55),'No bets, prices or labels are recomputed');
// A current-day, confirmed edition supersedes the old preview without merging picks.
const current={...edition,previewEdition:false,highRisk:[],safeBets:[],interestingObjects:[]};
chosen=vis.selectEdition(current,edition,now);
assert.equal(chosen.groups.safe.length,0);
assert.equal(chosen.groups.high.length,0);
const ranked=Array.from({length:6},(_,i)=>({
  ...p('ranked'+i,i===0?'Czech Republic':'Home '+i,'Spain'),
  category:i===0?'standard':'safe',qualificationTier:'qualified'
}));
const rankedEdition={...current,finalSelection:{version:40,rankedRecommendations:true},
  recommendations:ranked,safeBets:[ranked[1],p('alternate','Czechia','Spain'),
    p('remaining','Germany','Netherlands')]};
chosen=vis.selectEdition(rankedEdition,null,now);
assert.deepEqual(chosen.groups.qualified,ranked,'All ranked picks, including the sixth, are available');
assert.deepEqual(chosen.groups.safe.map(x=>x.matchId),['remaining']);
console.log('PASS: provider aliases, no duplicate fixtures, same-day preview, immutable odds');
