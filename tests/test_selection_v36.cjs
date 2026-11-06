'use strict';
// Legacy selection test migrated to the v40 shared display projection.
const assert=require('node:assert/strict');
const {selectEdition}=require('../site/visible-selection-v40.js');
const date='2026-11-06',at=new Date('2026-11-06T12:00:00Z');
const pick=(id,market,category)=>({matchId:id,home:'Home'+id,away:'Away'+id,
  kickoff:'2026-11-06T20:00:00Z',market,label:market,price:2.5,category});
const data={editionDate:date,finalSelection:{version:40},safeBets:[pick('a','H','safe')],
  highRisk:[pick('b','U25','high')],interestingObjects:[pick('c','BTTS','watch')]};
let output=selectEdition(data,null,at);
assert.deepEqual(output.groups.safe.map(x=>x.matchId),['a']);
assert.deepEqual(output.groups.high.map(x=>x.matchId),['b']);
assert.deepEqual(output.groups.watch.map(x=>x.matchId),['c']);
assert.equal(selectEdition({...data,finalSelection:{}},null,at).groups.safe.length,0);
console.log('PASS v36/v40: authoritative categories with no frontend re-ranking');
