#!/bin/bash
# macOS installer for the narrow v2.1 quality-model patch.
# Does not delete folders, snapshots, history or Git metadata.
set -e
PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 mangler. Installer Python 3 foerst, eller bruk GitHub Desktop og Terminal."
  read -rp "Trykk Enter for aa lukke: " _
  exit 1
fi
if [ -f "$PACKAGE_DIR/scripts/build_data.py" ] && [ -d "$PACKAGE_DIR/.git" ]; then
  DEST="$PACKAGE_DIR"
else
  DEST=""
  for candidate in "$HOME/Documents/GitHub/OddsGeneratoren3000" "$HOME/GitHub/OddsGeneratoren3000" "$HOME/Documents/OddsGeneratoren3000"; do
    if [ -f "$candidate/scripts/build_data.py" ] && [ -d "$candidate/.git" ]; then
      DEST="$candidate"
      break
    fi
  done
  if [ -z "$DEST" ]; then
    echo "Finn prosjektmappen OddsGeneratoren3000 i Finder."
    echo "Dra hele prosjektmappen inn i dette Terminal-vinduet og trykk Enter:"
    read -r DEST
    # Finder may escape spaces when dragging a path.
    DEST="${DEST//\\ / }"
    DEST="${DEST%/}"
    if [[ "$DEST" == \"*\" ]]; then DEST="${DEST:1:-1}"; fi
  fi
  if [ ! -f "$DEST/scripts/build_data.py" ] || [ ! -d "$DEST/.git" ]; then
    echo "FEIL: Finner ikke et ekte GitHub-prosjekt i valgt mappe. Ingen filer endret."
    read -rp "Trykk Enter for aa lukke: " _
    exit 1
  fi
  echo "Installerer i: $DEST"
  for file in scripts/form_v21.py scripts/quality_v20.py scripts/qualify_v20.py site/quality-v20.js tests/test_form_v21.py install_v21.py README_v21.md; do
    mkdir -p "$DEST/$(dirname "$file")"
    cp "$PACKAGE_DIR/$file" "$DEST/$file"
  done
fi
cd "$DEST"
set +e
python3 install_v21.py
status=$?
set -e
echo
if [ "$status" -eq 0 ]; then
  echo "Oppdateringen er installert lokalt. Gaa til GitHub Desktop og velg Commit + Push origin."
else
  echo "Oppdateringen er IKKE klar til aa pushes. Se feilmeldingen ovenfor."
fi
read -rp "Trykk Enter for aa lukke dette vinduet: " _
exit "$status"
