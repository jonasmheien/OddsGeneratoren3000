/* Runs the real published card/analysis renderer against verified mock records. */
'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('path').join(__dirname,'../site/three-fields-v26.js'),'utf8');
const anchor="  document.addEventListener('DOMContentLoaded',()=>{";
assert.equal(source.split(anchor).length,2);
const script=source.replace(anchor,"  globalThis.__formV38 = {card,analysisDetails};\n"+anchor);
const sandbox={document:{addEventListener(){}},Date,Intl,Number,Math,Array,Set,Object,String};
vm.createContext(sandbox);vm.runInContext(script,sandbox,{timeout:3000});
const {card}=sandbox.__formV38;
const rec=(id,at,home,away,hg,ag,side,status)=>({
  matchId:id,source:'football-data.org',sourceMatchId:id,kickoffUtc:at,
  homeTeam:{id:1,name:home},awayTeam:{id:2,name:away},homeGoals:hg,awayGoals:ag,
  analyzedTeamSide:side,resultForAnalyzedTeam:side==='home'?(hg>ag?'W':hg<ag?'L':'D'):(ag>hg?'W':ag<hg?'L':'D'),
  status:status||'FINISHED',verified:true,
});
const model={id:'f',home:'Brann',away:'Viking',formHome:'W',formAway:'W',
 formMatchesHome:[rec('1','2026-11-04T17:00:00Z','Brann','Molde',2,1,'home')],
 formMatchesAway:[rec('2','2026-11-03T17:00:00Z','Rosenborg','Viking',0,2,'away')],
 model:{probabilities:{B:.31}}};
const p={matchId:'f',home:'Brann',away:'Viking',kickoff:'2026-11-06T19:00:00Z',market:'B',label:'Borteseier',price:3.5,_candidateType:'model'};
let html=card(p,true,{editionDate:'2026-11-06',matches:[model]});
for(const part of ['HJEMMELAG','BORTELAG','Siste 5 kamper, alle arenaer','Brann','Rosenborg','Molde','Viking','2–1','0–2','04.11.2026','03.11.2026'])
 assert.ok(html.includes(part),part);
assert.ok(html.includes('tf-form-badge tf-form-W'));
assert.ok(html.includes('football-data.org'));
model.formMatchesHome=[rec('bad','2026-11-04T17:00:00Z','Brann','Molde',2,1,'home','IN_PLAY')];
html=card(p,true,{editionDate:'2026-11-06',matches:[model]});
assert.ok(!html.includes('Brann <b>2–1</b> Molde'));
assert.ok(html.includes('Ingen verifiserbare kampdetaljer'));
assert.ok(!html.includes('Eldre utgave:')); 
model.formMatchesHome=[rec('xss','2026-11-04T17:00:00Z','Brann','<script>x</script>',2,1,'home')];
html=card(p,true,{editionDate:'2026-11-06',matches:[model]});
assert.ok(html.includes('&lt;script&gt;x&lt;/script&gt;'));
assert.ok(!html.includes('<script>x</script>'));
console.log('PASS form v38: real fixtures, correct away perspective, legacy fallback, escaping');
