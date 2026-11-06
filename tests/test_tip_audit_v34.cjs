'use strict';
/* Synthetic archive regression; exact shared v40 projection is the source. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {archiveSnapshot,selectAsDisplayed}=require('../scripts/capture_visible_v34.cjs');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'ogv40-'));
const date='2026-11-06', now=new Date('2026-11-06T12:01:00Z');
const qt='2026-11-06T12:00:00Z', ko='2026-11-06T20:00:00Z';
const mk=(id,market,cat)=>({matchId:id,home:'Home'+id,away:'Away'+id,
    league:'Test',kickoff:ko,market,label:market,price:cat==='safe'?1.5:2.5,
    bookmakers:5,oddsUpdatedAt:qt,category:cat,qualificationTier:'market',
    _candidateType:'market',rationale:['Markedskandidat']});
const safe=mk('a','H','safe'),high=mk('b','U25','high'),watch=mk('c','BTTS','watch');
const q=(price)=>({price,books:5,lastUpdated:qt});
const matches=[safe,high,watch].map(p=>({id:p.matchId,home:p.home,away:p.away,
    kickoff:ko,league:'Test',odds:{[p.market]:q(p.price)},model:null}));
const edition={editionDate:date,localDate:date,generatedAt:qt,finalSelection:{version:40},
    matches,recommendations:[],safeBets:[safe],highRisk:[high],interestingObjects:[watch]};
const write=(f,obj)=>{fs.mkdirSync(path.dirname(f),{recursive:true});fs.writeFileSync(f,JSON.stringify(obj));};
const read=f=>JSON.parse(fs.readFileSync(f,'utf8'));
try{
 write(path.join(temp,'site/data/today.json'),edition);
 const expected=selectAsDisplayed(edition,null,null,now);
 const result=archiveSnapshot(temp,{now});
 assert.equal(result.changed,true);
 assert.equal(result.summary.total,3);
 const archive=path.join(temp,'state/tip-audit-v34/'+date+'.json');
 const groups=read(archive).revisions[0].groups;
 for(const category of ['safe','high','watch']){
   assert.deepEqual(groups[category].map(x=>x.market),expected.groups[category].map(x=>x.market));
   assert.deepEqual(groups[category].map(x=>x.matchId),expected.groups[category].map(x=>x.matchId));
 }
 assert.equal(archiveSnapshot(temp,{now}).changed,false,'same revision not repeated');
 assert.equal(archiveSnapshot(temp,{now:new Date('2026-11-06T21:00:00Z')}).changed,false,'past kickoff not archived');
 const newer={...edition,generatedAt:'2026-11-06T13:00:00Z',highRisk:[{...high,price:2.6}]};
 write(path.join(temp,'site/data/today.json'),newer);
 assert.equal(archiveSnapshot(temp,{now}).changed,true);
 assert.equal(read(archive).revisions.length,2);
 assert.equal(read(archive).revisions[0].groups.high[0].price,2.5,'old revision unchanged');
 console.log('PASS v34/v40: archive exactly matches UI visibility, idempotent, immutable revisions');
}finally{fs.rmSync(temp,{recursive:true,force:true});}
