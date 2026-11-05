/* No API calls. Verifies the published three-column UI with synthetic fixtures. */
'use strict';
const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const SRC=fs.readFileSync(require('path').join(__dirname,'../site/three-fields-v26.js'),'utf8');
const CLOCK='2026-11-05T14:00:00Z';
const KICKOFF='2026-11-05T20:00:00Z';
const UPDATED='2026-11-05T13:00:00Z';
function fixture(i, kind){
  const q=(price,books=12)=>({price,books,lastUpdated:UPDATED,source:'Test API'});
  const odds=kind==='safe'?{H:q(1.5),U:q(4.2),B:q(7)}:
    kind==='high'?{H:q(2.1),U:q(3.7),B:q(3.2)}:
    {H:q(2.65),U:q(3.55),B:q(2.85)};
  return {id:'test:'+i,home:'Lag H '+i,away:'Lag B '+i,kickoff:KICKOFF,
    league:'Testliga',status:'SCHEDULED',odds,
    model:kind==='high'?{sample:[11,10],effectiveSample:[7,7],probabilities:{B:.33}}:null};
}
function snapshot(){
  const matches=[...Array.from({length:5},(_,i)=>fixture(i,'safe')),
    ...Array.from({length:3},(_,i)=>fixture(i+5,'high')),
    ...Array.from({length:5},(_,i)=>fixture(i+8,'market'))];
  // A strict candidate must be shown first and never repeated in another area.
  const strict={matchId:'test:5',home:'Lag H 5',away:'Lag B 5',league:'Testliga',
    kickoff:KICKOFF,market:'B',label:'Borteseier',price:3.2,category:'high',
    bookmakers:12,oddsUpdatedAt:UPDATED,conservativeEdge:.05,rationale:['Strengt kvalifisert']};
  return {editionDate:'2026-11-05',generatedAt:UPDATED,matches,recommendations:[strict],
    safeBets:[],highRisk:[],observations:[]};
}
function fakeDate(now){return class extends Date{
  constructor(...args){super(...(args.length?args:[now]))}
  static now(){return +new Date(now)}
}}
async function render(data,{now=CLOCK,preview=null}={}){
  const state=new Map();
  function el(id){if(!state.has(id))state.set(id,{id,textContent:'',innerHTML:'',querySelectorAll:()=>[],addEventListener:()=>{}});return state.get(id)}
  const document={body:{classList:{add(){}}},visibilityState:'visible',getElementById:el,
    createElement:()=>({innerHTML:'',id:'',className:''}),
    querySelector:()=>({querySelector:()=>({after(){}}),prepend(){}}),
    addEventListener:(ev,fn)=>{if(ev==='DOMContentLoaded')fn()}};
  const fetch=async u=>({ok:true,json:async()=>u.includes('tomorrow')?preview:data});
  const env={document,Date:fakeDate(now),fetch,setInterval(){},Intl,Set,Number,String,Object,Array,Math,JSON,Promise};
  vm.runInNewContext(SRC,env,{timeout:3000});
  for(let i=0;i<5;i++)await new Promise(setImmediate);
  return {count:k=>Number(el('tf-'+k+'-count').textContent),
    html:k=>el('tf-'+k+'-list').innerHTML,
    date:el('tf-date').textContent,status:el('tf-status').textContent};
}
(async()=>{
  const a=await render(snapshot());
  assert.equal(a.count('high'),5,'High Risk must contain 5 sourced candidates');
  assert.equal(a.count('safe'),5,'Safe Bets must contain 5 sourced candidates');
  assert.ok(a.html('high').includes('Strengt kvalifisert'),'qualified candidate first');
  assert.ok(a.html('high').includes('Markedsbasert High Risk'),'risk quote fallback labeled');
  assert.ok(a.html('safe').includes('Markedsbasert Safe Bet'),'safe quote fallback labeled');
  assert.ok(a.html('high').includes('Vis analysen'),'analysis available');
  assert.ok(!a.html('safe').includes('Lag H 5'),'no duplicate strict pick in safe');
  assert.equal((a.html('high').match(/class="tf-card"/g)||[]).length,5);
  const stale=snapshot();stale.matches.forEach(m=>Object.values(m.odds).forEach(q=>q.lastUpdated='2026-11-04T00:00:00Z'));
  stale.recommendations[0].oddsUpdatedAt='2026-11-04T00:00:00Z';
  const b=await render(stale);
  assert.equal(b.count('high'),0,'stale odds must be hidden');
  assert.equal(b.count('safe'),0,'stale odds must be hidden');
  const c=await render(snapshot(),{now:'2026-11-05T20:01:00Z'});
  assert.equal(c.count('high'),0,'started matches must be hidden');
  assert.equal(c.count('safe'),0,'started matches must be hidden');
  const empty=await render({editionDate:'2026-11-05',recommendations:[],matches:[]});
  assert.equal(empty.count('high'),0);assert.equal(empty.count('safe'),0);
  console.log('PASS: 5+5, provenance, analyses, no overlap, stale quotes, kickoff, empty day');
})().catch(e=>{console.error(e);process.exitCode=1});
