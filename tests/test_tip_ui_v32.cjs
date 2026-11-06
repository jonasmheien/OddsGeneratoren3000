'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {selectEdition}=require('../site/visible-selection-v40.js');
const code=fs.readFileSync(path.resolve(__dirname,'../site/three-fields-v26.js'),'utf8');
assert.match(code,/OddsVisibleV40\?\.selectEdition/);
assert.doesNotMatch(code,/function safeMarketCandidates\(/);
assert.doesNotMatch(code,/function highModelCandidates\(/);
assert.doesNotMatch(code,/function highMarketCandidates\(/);
const at=new Date('2026-11-06T12:00:00Z');
const p=i=>({matchId:'x'+i,home:'Home',away:'Away',market:'H',label:'Hjemmeseier',
  price:1.5,kickoff:'2026-11-06T20:00:00Z'});
const a={editionDate:'2026-11-06',finalSelection:{version:40},
 safeBets:Array.from({length:5},(_,i)=>p(i)),highRisk:[p(8)],interestingObjects:[]};
const shown=selectEdition(a,null,at);
assert.equal(shown.groups.safe.length,5);
assert.equal(shown.groups.high.length,1);
assert.equal(shown.groups.watch.length,0);
console.log('PASS v32/v40: no browser-supplied candidates, backend sections displayed unchanged');
