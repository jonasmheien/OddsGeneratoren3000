'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('site/three-fields-v26.js','utf8')
  .replace('  let parent;','  let parent=globalThis.__parent;')
  .replace("  document.addEventListener('DOMContentLoaded',()=>{",
    "  globalThis.__load=load;\n  document.addEventListener('DOMContentLoaded',()=>{");
const instant='2026-11-19T10:00:00Z';
class Clock extends Date {
  constructor(...args){super(...(args.length?args:[instant]));}
  static now(){return +new Date(instant);}
}
async function render(reason,{day='2026-11-19',tips=false,missing=false}={}){
  const nodes=new Map(),columns={hidden:false};
  const node=id=>{
    if(!nodes.has(id))nodes.set(id,{textContent:'',hidden:false,innerHTML:'',querySelectorAll:()=>[],querySelector:()=>null});
    return nodes.get(id);
  };
  const pick={matchId:'same',home:'Home',away:'Away',market:'H',label:'Hjemmeseier',price:1.7,kickoff:'2026-11-19T20:00:00Z'};
  const edition={editionDate:'2026-11-19',generatedAt:instant};
  const values={today:missing?null:edition,tomorrow:null,'update-status-v51':null,
    'operations-v55':{schemaVersion:55,targetDate:day,reason}};
  const sandbox={Date:Clock,Intl,Number,Math,Array,Set,Object,String,
    document:{getElementById:node,addEventListener(){}},
    __parent:{querySelector:()=>columns},
    window:{OddsVisibleV40:{selectEdition:()=>tips?{edition,groups:{safe:[pick],high:[],watch:[]}}:null}},
    fetch:async url=>({ok:true,json:async()=>values[/data\/([^.?]+)/.exec(url)[1]]})};
  vm.createContext(sandbox);vm.runInContext(source,sandbox);await sandbox.__load();
  return {text:node('tf-status').textContent,hidden:node('tf-status').hidden,columns:columns.hidden,
    cards:node('tf-safe-list').innerHTML};
}
(async()=>{
  assert.equal((await render('source_error')).text,'Datakilden er midlertidig utilgjengelig.');
  assert.equal((await render('coverage_limited')).text,'Ingen odds for dagens kamper.');
  assert.equal((await render('waiting_for_odds')).text,'Venter på odds.');
  assert.equal((await render('quota_limited')).text,'Avventer tilgjengelig oddskvote.');
  assert.equal((await render('source_error',{day:'2026-11-18'})).text,'Ingen kommende tips.');
  assert.equal((await render('ready',{tips:true})).hidden,true);
  const failed=await render('source_error',{tips:true});
  assert.equal(failed.columns,false);
  assert.match(failed.cards,/Home.*Away/);
  assert.equal((await render('source_error',{missing:true})).text,'Tipsene kunne ikke lastes.');
  console.log('PASS: current acquisition status, stale-status rejection and preserved published tips');
})().catch(error=>{console.error(error);process.exitCode=1;});
