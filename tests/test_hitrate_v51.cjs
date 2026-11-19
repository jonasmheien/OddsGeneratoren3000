'use strict';
const assert=require('node:assert/strict');
const {markup,filtered,rows}=require('../site/hitrate-v51.js');
const stats={total:5,wins:2,losses:1,settled:3,voids:0,pending:1,unverified:1,hitRatePct:66.7};
const report={overall:stats,categories:{safe:stats},tips:[
  {category:'safe',home:'Home <script>',away:'Away',label:'Hjemmeseier',result:{status:'won'}},
  {category:'high',home:'Home',away:'Away',label:'Borteseier',result:{status:'unverified'}}]};
const html=markup(report);
assert.match(html,/2 av 3 avgjorte/);
assert.match(html,/66,7 %/);
assert.doesNotMatch(html,/venter ·|Kvalifiserte|Vunnet delt/);
assert.match(html,/Første tips per kamp/);
assert.equal((html.match(/class="hr51-card"/g)||[]).length,3);
assert.match(html,/Ingen avgjorte/,'an empty category never claims a zero-percent losing record');
assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
assert.equal(filtered(report.tips,'safe','won').length,1);
assert.equal(filtered(report.tips,'high','lost').length,0);
assert.match(rows(filtered(report.tips,'high','lost')),/Ingen tips med dette filteret/);
assert.equal(filtered([{result:{status:'live'}},{result:{status:'postponed'}}],'all','pending').length,2);
console.log('PASS: per-category denominators, unknown outcomes, filters and escaped tip log');
