// Focused tests: exact three sections, only verified history, probability provenance.
'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
let src=fs.readFileSync(require('path').join(__dirname,'../site/three-fields-v26.js'),'utf8');
const anchor="  document.addEventListener('DOMContentLoaded',()=>{";
assert.equal(src.split(anchor).length,2);
src=src.replace(anchor,"  globalThis.__analysisTest = {analysisDetails,card};\n"+anchor);
const sandbox={document:{addEventListener(){}},Date,Intl,Number,Math,Array,Set,Object,String};
vm.createContext(sandbox);vm.runInContext(src,sandbox);
const {card}=sandbox.__analysisTest;
const match={id:'m1',home:'Brann',away:'Viking',
  formHome:'WWLDLDD',formAway:'DLWWLLW',
  model:{probabilities:{B:.3717}},
  odds:{B:{price:3.1,books:12,lastUpdated:'2026-11-05T10:00:00Z'}}};
const edition={editionDate:'2026-11-05',matches:[match]};
const common={matchId:'m1',home:'Brann',away:'Viking',kickoff:'2026-11-05T20:00:00Z',market:'B',label:'Borteseier',price:3.1};
const block=html=>html.split('<div class="tf-analysis-body tf-analysis-compact">')[1].split('</details>')[0];
let result=block(card({...common,_candidateType:'model',probability:.3717},true,edition));
assert.ok(result.includes('<h3>Vurdering</h3>'));
assert.ok(result.includes('Siste fem kamper'));
assert.ok(result.includes('Sannsynlighet for spillet'));
assert.ok(result.includes('37,2 %'));
assert.ok(result.includes('Formmodell, ikke historisk kalibrert'));
assert.equal((result.match(/class="tf-form-badge tf-form-/g)||[]).length,10,'exactly five real results per team');
assert.ok(result.includes('tf-form-W" title="Seier"') && result.includes('tf-form-L" title="Tap"'));
for(const unused of ['Datagrunnlag','Forventede mål','Antall bookmakere','Beregnet verdi i scenario','Hvorfor dette spillet?'])assert.ok(!result.includes(unused),unused);
const expert=block(card({...common,expertReason:'Analysen støtter X',expertSource:'En navngitt ekspert'},true,edition));
assert.ok(expert.includes('Ekspertens begrunnelse'));
assert.ok(expert.includes('En navngitt ekspert'));
const noProvenance=block(card({...common,_candidateType:'market',probability:.63},true,edition));
assert.ok(!noProvenance.includes('Ekspertens begrunnelse'));
assert.ok(noProvenance.includes('63 %'));
assert.ok(noProvenance.includes('Anslått fra bookmakerodds uten margin'));
const missing=block(card({...common,home:'<script>x</script>',away:'Viking'},false,{editionDate:'2026-11-05',matches:[]}));
assert.ok(missing.includes('&lt;script&gt;x&lt;/script&gt;'));
assert.ok(!missing.includes('<script>x</script>'));
assert.ok(missing.includes('Ingen registrert kampform'));
assert.ok(missing.includes('Ikke beregnet'));
console.log('PASS: compact analysis, newest 5, sources, missing data and escaping');
