#!/usr/bin/env python3
"""Apply a narrowly scoped v2.1 patch to the currently checked-out repository.

Fails closed if upstream code has changed. Does not edit any user data,
result history, environment files or deployment configuration.
"""
from __future__ import annotations

import compileall
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / 'scripts' / 'build_data.py'
PATCHED_MARKER = "'modelMethod'] = 'strength_adjusted_v21'"

REPLACEMENTS = (
    ("from recommend import curated_picks, category_picks",
     "from recommend import curated_picks, category_picks\nfrom form_v21 import adjusted_form, effective_form_sample, opponent_indices"),
    ("def recent_team_form(matches: list, before: datetime, team_id: int, limit: int = 6)",
     "def recent_team_form(matches: list, before: datetime, team_id: int, limit: int = 16)"),
    ("values.append((kickoff, gf, ga, 'W' if gf > ga else 'D' if gf == ga else 'L'))",
     "values.append((kickoff, gf, ga, 'W' if gf > ga else 'D' if gf == ga else 'L', away if ish else home))"),
    ("    output = []\n    for raw in fixtures:",
     "    output = []\n    strengths = opponent_indices(fixtures, now)\n    for raw in fixtures:"),
    ("'model': model_probabilities(hf, af), 'odds': {}, 'predictions': []}",
     "'model': model_probabilities(adjusted_form(hf, strengths, k), adjusted_form(af, strengths, k)), 'odds': {}, 'predictions': []}\n"
     "        if m['model'] is not None:\n"
     "            m['model']['effectiveSample'] = [effective_form_sample(hf, k), effective_form_sample(af, k)]\n"
     "            m['model']['modelMethod'] = 'strength_adjusted_v21'\n"
     "            m['model']['historyWindowDays'] = 180"),
    ("timedelta(days=75)", "timedelta(days=180)"),
    ("timedelta(days=85)", "timedelta(days=180)"),
)


def main():
    if not TARGET.is_file():
        raise SystemExit('FEIL: Kjør fra rotmappen til OddsGeneratoren-repoet (scripts/build_data.py mangler).')
    for relative in ('scripts/form_v21.py','scripts/quality_v20.py','scripts/qualify_v20.py',
                     'site/quality-v20.js', 'tests/test_form_v21.py'):
        if not (ROOT / relative).is_file():
            raise SystemExit('FEIL: Mangler filen '+relative+'. Kopier hele oppdateringspakken først.')
    original = TARGET.read_text(encoding='utf-8')
    if PATCHED_MARKER in original:
        print('Modellen var allerede oppdatert. Kontrollerer testene på nytt.')
        patched = original
    else:
        patched = original
        for before, after in REPLACEMENTS:
            if patched.count(before) != 1:
                raise SystemExit('FEIL: Forventet eksisterende kodelinje ikke funnet nøyaktig én gang:\n'+before+
                                 '\nIngen originalfiler er endret. Kontakt oss for tilpasset oppdatering.')
            patched = patched.replace(before, after, 1)
    compile(patched, str(TARGET), 'exec')
    if patched != original:
        backup = Path.home() / '.odds_generatoren_backups'
        backup.mkdir(exist_ok=True)
        destination = backup / ('build_data_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.py')
        shutil.copy2(TARGET, destination)
        TARGET.write_text(patched, encoding='utf-8')
        print('Modellen oppdatert. Sikkerhetskopi lagret utenfor prosjektet.')
    print('Tester alle moduler ...')
    check = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'], cwd=ROOT)
    if check.returncode != 0:
        if patched != original:
            TARGET.write_text(original, encoding='utf-8')
        raise SystemExit('FEIL: En test mislyktes. Den opprinnelige byggemotoren er gjenopprettet. Ikke push.')
    # Only request an automatic new edition after validated installation.
    signal = ROOT / '.github' / 'refresh-once-v15'
    if not signal.exists():
        signal.parent.mkdir(parents=True, exist_ok=True)
        signal.write_text('REFRESH_ON_NEXT_PUSH\n', encoding='utf-8')
    elif signal.read_text(encoding='utf-8').strip() != 'REFRESH_ON_NEXT_PUSH':
        raise SystemExit('FEIL: Ukjent oppdateringsmarkør i .github. Ikke push før den er gjennomgått.')
    print('KLART: Alle tester bestått. Åpne GitHub Desktop, se gjennom endringene, Commit og Push.')
    print('Neste push forsøker én ny dagsanalyse med v2.1. Eksisterende historie blir ikke overskrevet.')


if __name__ == '__main__':
    main()
