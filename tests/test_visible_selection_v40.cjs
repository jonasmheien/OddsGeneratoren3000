'use strict';
const assert=require('node:assert/strict');
const {selectEdition,upcoming}=require('../site/visible-selection-v40.js');
const date='2026-11-06',now=new Date('2026-11-06T12:01:00Z');
const kickoff='2026-11-06T20:00:00Z';
const p=(id,market,group)=>({matchId:id,home:'Home'+id,away:'Away'+id,
  league:'Test',kickoff,market,label:'Marked '+market,price:1.8,qualificationTier:group});
const old={editionDate:date,safeBets:[p('a','O25','market')],highRisk:[],interestingObjects:[]};
let result=selectEdition(old,null,now);
assert.equal(result.groups.safe.length,0,'Old JSON cannot trigger client generated picks');
assert.equal(result.authoritative,false);
const latest={...old,finalSelection:{version:40},safeBets:[p('a','O25','market')],
  highRisk:[p('b','U25','qualified')],interestingObjects:[p('c','BTTS','observation')]};
result=selectEdition(latest,null,now);
assert.equal(result.groups.safe.length,1);
assert.equal(result.groups.high.length,1);
assert.equal(result.groups.watch.length,1);
assert.equal(result.groups.safe[0],latest.safeBets[0],'No new objects, same backend identity');
assert.equal(selectEdition(latest,null,new Date('2026-11-06T21:00:00Z')).groups.safe.length,0);
assert.equal(selectEdition(latest,null,new Date('2026-11-07T12:01:00Z')).groups.safe.length,0);
assert.equal(upcoming({...latest.safeBets[0],label:''},latest,now),false);
const shifted={...latest,editionDate:'2026-11-07',localDate:'2026-11-07',
  previewEdition:true,safeBets:[{...p('d','O25','market'),kickoff:'2026-11-07T20:00:00Z'}],
  highRisk:[],interestingObjects:[]};
assert.equal(selectEdition(latest,shifted,new Date('2026-11-06T21:00:00Z')).source,'tomorrow');
console.log('PASS v40: backend-only display, past and started matches filtered, preview and invalid data');
