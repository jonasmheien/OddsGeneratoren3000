"""Regression tests for the simplified, evidence-aware analysis display."""
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
        for label in ('High Risk','Safe Bets','Interessante objekter'):
            self.assertIn(label,code)
        self.assertEqual(code.count('class="tf-section"'),3)
        self.assertIn('three-v26',code)

    def test_compact_analysis_only(self):
        code=JS.read_text(encoding='utf-8')
        section=code.split('  function analysisDetails(p,recommended,edition){',1)[1].split('  function card(p,recommended,edition){',1)[0]
        for item in ('Vis analysen','Skjul analysen','Siste fem kamper','Sannsynlighet for spillet','Ekspertens begrunnelse','Vurdering','tf-probability'):
            self.assertIn(item,section)
        for old in ('Datagrunnlag','Forventede mål','Antall bookmakere','Beregnet verdi i scenario','tf-analysis-warning','tf-analysis-sources'):
            self.assertNotIn(old,section)
        self.assertRegex(HTML.read_text(encoding='utf-8'), r'three-fields-v26\.js\?v=\d+')
        self.assertRegex(HTML.read_text(encoding='utf-8'), r'three-fields-v26\.css\?v=\d+')
        self.assertIn('tf-form-badge',CSS.read_text(encoding='utf-8'))

    @unittest.skipUnless(shutil.which('node'),'Node.js unavailable')
    def test_real_js_rendering_and_escaping(self):
        subprocess.run(['node','tests/test_analysis_compact_v33.cjs'],cwd=ROOT,check=True,capture_output=True,text=True)

if __name__=='__main__':
    unittest.main()
