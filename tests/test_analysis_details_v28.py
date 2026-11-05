"""Guards for the compact, fact-backed 'Vis analysen' extension."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JS=ROOT/'site/three-fields-v26.js'
CSS=ROOT/'site/three-fields-v26.css'
HTML=ROOT/'site/index.html'


class AnalysisDetailsV28(unittest.TestCase):
    def test_three_fields_stay_the_only_sections(self):
        code=JS.read_text(encoding='utf-8')
        for item in ('High Risk','Safe Bets','Interessante objekter'):
            self.assertIn(item, code)
        self.assertEqual(code.count('class="tf-section"'),3)
        self.assertIn('three-v26', code)

    def test_detail_data_is_traceable_and_collapsible(self):
        code=JS.read_text(encoding='utf-8')
        for part in ('<details class="tf-analysis"','<summary>','Vis analysen','Skjul analysen',
                     'match?.model','model?.sample','model?.expectedGoals',
                     'p.oddsUpdatedAt ?? quote?.lastUpdated','p.rationale',
                     'Ingen verifisert, komplett formmodell',
                     'entries.map(p=>card(p,id!==\'watch\',edition))',
                     "querySelectorAll('details.tf-analysis[open]')"):
            self.assertIn(part,code)
        self.assertIn('tf-analysis summary:focus-visible',CSS.read_text(encoding='utf-8'))
        self.assertIn('three-fields-v26.js?v=31',HTML.read_text(encoding='utf-8'))
        self.assertIn('three-fields-v26.css?v=28',HTML.read_text(encoding='utf-8'))

    @unittest.skipUnless(shutil.which('node'),'Node.js unavailable')
    def test_real_js_rendering_and_escaping(self):
        script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
let src=fs.readFileSync(process.argv[1],'utf8');
const entry="  document.addEventListener('DOMContentLoaded',()=>{";
assert.equal(src.split(entry).length,2);
src=src.replace(entry,"  globalThis.__test = {card};\n"+entry);
const ctx={document:{addEventListener:()=>{}},Intl,Date,Number,Array,String,Object,Set};
vm.createContext(ctx);vm.runInContext(src,ctx);
const card=ctx.__test.card;
const m={id:'a1',formHome:'WLDDW',formAway:'WDWLL',model:{sample:[11,9],expectedGoals:[1.35,1.35],probabilities:{B:.3717}},odds:{B:{price:4.78,books:20,lastUpdated:'2026-11-05T08:07:57Z'}},predictions:[{source:'API-Football Predictions',probabilities:{B:.1}}]};
const e={editionDate:'2026-11-05',matches:[m]};
const p={matchId:'a1',home:'Home',away:'Away',market:'B',label:'Away win',price:4.78,reason:'Ikke anbefalt'};
let html=card(p,false,e);
for(const x of ['Vis analysen','Skjul analysen','11 hjemmelag / 9 bortelag','1,35 / 1,35','37,2 %','Hvorfor ikke anbefalt?','API-Football Predictions'])assert.ok(html.includes(x),x);
html=card({...p,conservativeEdge:.05,conservativeProbability:.31,rationale:['Model says so']},true,e);
for(const x of ['+5 %','31 %','Hvorfor dette spillet?','Model says so'])assert.ok(html.includes(x),x);
html=card({...p,home:'<svg/onload=1>',label:'<script>x</script>',reason:'<img src=x>'},false,{editionDate:'2026-11-05',matches:[]});
assert.ok(html.includes('&lt;svg/onload=1&gt;'));
assert.ok(html.includes('&lt;script&gt;x&lt;/script&gt;'));
assert.ok(!html.includes('<script>x</script>'));
assert.ok(html.includes('Ingen verifisert, komplett formmodell'));
assert.ok(!html.includes('37,2 %'));
'''
        subprocess.run(['node','-e',script,str(JS)],cwd=ROOT,check=True,capture_output=True,text=True)


if __name__=='__main__':
    unittest.main()
