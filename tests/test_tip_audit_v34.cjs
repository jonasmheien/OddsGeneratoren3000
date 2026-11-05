'use strict';
/* Regression tests use synthetic fixtures. No external API or Github writes. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {archiveSnapshot,getPicker,selectAsDisplayed}=require('../scripts/capture_visible_v34.cjs');
const ROOT=path.resolve(__dirname,'..');
const UI=path.join(ROOT,'site/three-fields-v26.js');
const t=fs.mkdtempSync(path.join(os.tmpdir(),'odds-v34-'));
const date='2026-11-06';
const NOW='2026-11-06T12:01:00.000Z';
const quoteTime='2026-11-06T12:00:00Z';
const kickoff='2026-11-06T20:00:00Z';
function q(price){return {price,books:11,lastUpdated:quoteTime,source:'Test bookmaker'};}
function match(i){
  const kind=i<5?'safe':i<10?'model':'watch';
  return {id:'case-'+i,home:'H'+i,away:'A'+i,league:'Test League',kickoff,
    status:'SCHEDULED',formHome:i===1?'':'WWDLWWW',formAway:i===2?'':'LDWWL',
    odds:kind==='safe'?{H:q(1.5),U:q(4.2),B:q(7)}:
         kind==='model'?{H:q(2.1),U:q(3.7),B:q(3.2)}:
         {H:q(2.65),U:q(3.55),B:q(2.85)},
    model:kind==='model'?{sample:[11,10],effectiveSample:[7,7],probabilities:{B:.33}}:null,
    predictions:[]};
}
const edition={editionDate:date,localDate:date,generatedAt:NOW,matches:Array.from({length:15},(_,i)=>match(i)),recommendations:[],observations:[]};
const read=file=>JSON.parse(fs.readFileSync(file,'utf8'));
function writeJson(file,obj){fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(obj));}
try{
  fs.mkdirSync(path.join(t,'site'),{recursive:true});
  fs.copyFileSync(UI,path.join(t,'site/three-fields-v26.js'));
  writeJson(path.join(t,'site/data/today.json'),edition);
  const now=new Date(NOW);
  const picker=getPicker(UI,now);
  const expected=selectAsDisplayed(edition,null,picker,now);
  const res=archiveSnapshot(t,{now});
  assert.equal(res.changed,true);
  assert.equal(res.summary.total,15);
  assert.equal(res.summary.high,5);
  assert.equal(res.summary.safe,5);
  assert.equal(res.summary.watch,5);
  const archiveFile=path.join(t,'state/tip-audit-v34/'+date+'.json');
  let journal=read(archiveFile);
  assert.equal(journal.revisions.length,1);
  for(const category of ['high','safe','watch']){
    assert.deepEqual(journal.revisions[0].groups[category].map(x=>x.matchId).join('|'),expected.groups[category].map(x=>x.matchId).join('|'),category+' matches published UI');
    assert.deepEqual(journal.revisions[0].groups[category].map(x=>x.market).join('|'),expected.groups[category].map(x=>x.market).join('|'),category+' markets published UI');
  }
  const all=Object.values(journal.revisions[0].groups).flat();
  assert.equal(new Set(all.map(x=>x.matchId)).size,15,'no duplicate fixtures across categories');
  assert.ok(all.some(x=>x.quality.issues.includes('home_form_missing')));
  assert.ok(all.some(x=>x.quality.issues.includes('away_form_missing')));
  assert.ok(all.some(x=>x.quality.evidenceTier==='form_and_model'));
  assert.ok(all.some(x=>x.sourceType==='bookmaker_market'&&x.probabilitySource==='no_vig_bookmaker_market'));
  assert.ok(all.every(x=>x.result.status==='not_verified'));
  assert.equal(all.filter(x=>x.quality.independentlySourcedWrittenExpert).length,0);
  const out=read(path.join(t,'site/data/tip-audit-v34.json'));
  assert.equal(out.revisionId,res.id);
  const second=archiveSnapshot(t,{now});
  assert.equal(second.changed,false);
  assert.equal(read(archiveFile).revisions.length,1,'idempotent publish, no daily duplication');

  // New afternoon edition: old quoted odds and selections must stay frozen.
  const originalPrice=read(archiveFile).revisions[0].groups.safe[0].price;
  edition.generatedAt='2026-11-06T15:20:00Z';
  edition.matches[0].odds.H=q(1.4);
  writeJson(path.join(t,'site/data/today.json'),edition);
  const later=archiveSnapshot(t,{now:new Date('2026-11-06T15:20:30Z')});
  assert.equal(later.changed,true);
  journal=read(archiveFile);
  assert.equal(journal.revisions.length,2);
  assert.equal(journal.revisions[0].groups.safe[0].price,originalPrice);
  assert.notEqual(journal.revisions[0].id,journal.revisions[1].id);

  // No new revision after kick-off; no stale/missing data manufacture.
  const finished=archiveSnapshot(t,{now:new Date('2026-11-06T20:03:00Z')});
  assert.equal(finished.changed,false);
  assert.equal(read(archiveFile).revisions.length,2);

  // Different local date must not silently attach picks to the wrong day.
  const next=archiveSnapshot(t,{now:new Date('2026-11-07T12:00:00Z')});
  assert.equal(next.changed,false);

  // Fail closed if UI picker signature changes, rather than recording different picks.
  fs.writeFileSync(path.join(t,'site/three-fields-v26.js'),'/* changed */');
  assert.throws(()=>archiveSnapshot(t,{now}),/UI selector anchor changed/);
  console.log('PASS: exact UI selection, immutable revisions, data quality, provenance, idempotence, kickoff, source guard');
}finally{
  fs.rmSync(t,{recursive:true,force:true});
}
