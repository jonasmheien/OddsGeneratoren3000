#!/usr/bin/env python3
"""Safely add a read-only daily tip journal to an existing OddsGeneratoren repo.

Run from the repo root (GitHub Desktop > Repository > Open in Terminal):
    python3 installer_v34.py
No external dependencies and no API calls. Verifies expected workflow anchors.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
WF = ROOT / '.github/workflows/publish.yml'
UI = ROOT / 'site/three-fields-v26.js'
SCRIPT = ROOT / 'scripts/capture_visible_v34.cjs'
TEST = ROOT / 'tests/test_tip_audit_v34.cjs'
MARKER = '      - name: Arkiver viste tips og kontroller datagrunnlag v34'


def replace_one(text: str, before: str, after: str) -> str:
    n = text.count(before)
    if n != 1:
        raise RuntimeError(f'Installering stoppet: fant {n} forekomster av forventet arbeidsflytmarkør {before!r}')
    return text.replace(before, after, 1)


def main() -> None:
    if not WF.is_file() or not UI.is_file() or not SCRIPT.is_file() or not TEST.is_file():
        raise RuntimeError('Åpne GitHub-repositoriet i Terminal og pakk ZIP-filen ut der først.')
    subprocess.run(['node', '--check', str(SCRIPT)], check=True, cwd=ROOT)
    subprocess.run(['node', str(TEST)], check=True, cwd=ROOT)

    before = WF.read_text(encoding='utf-8')
    if MARKER in before:
        print('Allerede installert. Testene besto. Ingen endringer nødvendig.')
        return
    after = before
    after = replace_one(after,
        '          node tests/test_tip_ui_v32.cjs\n',
        '          node tests/test_tip_ui_v32.cjs\n          node tests/test_tip_audit_v34.cjs\n')

    # The new step audits the SAME ranking as the site, and never changes tips.
    # A new supplemental failure cannot take the published page offline.
    extra = (
        '      - name: Arkiver viste tips og kontroller datagrunnlag v34\n'
        '        id: tip_audit\n'
        "        if: steps.trigger.outputs.mode != 'results'\n"
        '        continue-on-error: true\n'
        '        run: node scripts/capture_visible_v34.cjs\n'
    )
    after = replace_one(after,
        '      - name: Lagre den valgte utgaven og resultatene\n',
        extra + '      - name: Lagre den valgte utgaven og resultatene\n')
    after = replace_one(after,
        "        if: steps.trigger.outputs.mode != 'deploy'\n",
        "        if: steps.trigger.outputs.mode != 'deploy' || steps.tip_audit.outputs.changed == 'true'\n")
    after = replace_one(after,
        '          git add -A -- state/ site/data/today.json site/data/history.json site/data/versions.json\n',
        '          git add -A -- state/ site/data/today.json site/data/history.json site/data/versions.json\n'
        '          if [[ -f site/data/tip-audit-v34.json ]]; then\n'
        '            git add -A -- site/data/tip-audit-v34.json\n'
        '          fi\n')

    # Avoid worktree mutation on a failed anchor match or test.
    if after == before:
        raise RuntimeError('Ingenting ble endret i workflow')
    WF.write_text(after, encoding='utf-8')
    print('INSTALLERT: sporing av faktiske viste tips, uforanderlige dagsversjoner, datakvalitetsrapport.')
    print('UI og eksisterende tipsutvelgelse er IKKE endret.')
    print('Neste steg: GitHub Desktop > Commit to main > Push origin.')

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print('STOPPET: ' + str(exc), file=sys.stderr)
        sys.exit(1)
