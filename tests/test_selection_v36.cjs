// v36: match identity, Safe-first reservation, three distinct columns.
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.resolve(__dirname,'../site/three-fields-v26.js'),'utf8');
const anchor="  document.addEventListener('DOMContentLoaded',()=>{";
assert.equal(source.split(anchor).length,2);
const code=source.replace(anchor,"  globalThis.v36 = {featured,interesting,markUsed,gameToken};\n"+anchor);
const now=new Date('2026-11-06T12:01:00Z');
class Clock extends Date { constructor(...x){super(...(x.length?x:[now.getTime()]));}static now(){return now.getTime();} }
const context={document:{addEventListener(){}},Date:Clock,Intl,Math,Number,String,Array,Object,Set,JSON};
vm.createContext(context);vm.runInContext(code,context,{timeout:5000});
const p=context.v36;
const tm='2026-11-06T12:00:00Z';
const q=price=>({price,books:12,lastUpdated:tm});
const ko='2026-11-06T20:00:00Z';
const make=(id,home,away,odds,model)=>({id,home,away,kickoff:ko,league:'Test',odds,model});
const w=()=>({H:q(1.5),U:q(4.6),B:q(7.2)});
const long=()=>({H:q(2.5),U:q(3.6),B:q(2.9)});
const matches=[make('b1','Derby County','Bolton',long()),
    make('b2','Derby County','Bolton Wanderers',long()),
    make('s1','Lyn','Brann',w()),
    make('s2','Silkeborg','Lyngby',w()),
    make('s3','Silkeborg IF','Lyngby',w()),
    make('h4','Viking','Bodo',long()),
    make('h5','Hammarby','Djurgarden',long()),
    make('h6','Molde','Tromso',long()),
    make('w1','Trondheim','Bergen',long())];
const edition={editionDate:'2026-11-06',matches,recommendations:[],observations:[]};
const safe=p.featured(edition,'safe',now);
const used=new Set();for(const item of safe)p.markUsed(used,item);
const high=p.featured(edition,'high',now,used);
for(const item of high)p.markUsed(used,item);
const watch=p.interesting(edition,now,used);
const selected=[...safe,...high,...watch];
assert.ok(safe.length>=2,'safe selections have priority');
assert.equal(new Set(selected.map(p.gameToken)).size,selected.length,'no repeated real fixture across categories');
assert.ok(!selected.some(x=>x.home==='Silkeborg IF'&&selected.some(y=>y.home==='Silkeborg')));
assert.ok(!selected.some(x=>x.away==='Bolton Wanderers'&&selected.some(y=>y.away==='Bolton')));
assert.ok(safe.every(x=>x.price<=1.7),'never silently reduce low-risk constraints');
const oldDate={...edition,editionDate:'2026-11-05'};
assert.equal(p.featured(oldDate,'safe',now).length,0,'no wrong-day candidates');
console.log('PASS v36: Safe-first, alias dedup, exact date and unchanged price limits');
