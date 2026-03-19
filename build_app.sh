#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# build_app.sh — Baut die selbst-enthaltene Mac App mit PyInstaller
#
# Voraussetzung: Python 3 (nur für dich als Entwickler, NICHT für die Endnutzerin)
# Aufruf:  bash build_app.sh
#
# Ergebnis: dist/Rezept_Transcripts.zip
#           → Diese Datei per AirDrop / iCloud / E-Mail an deine Frau schicken
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo ""
echo "🔧  Abhängigkeiten installieren …"
pip3 install --quiet pyinstaller youtube-transcript-api

echo ""
echo "🏗️   App bauen (dauert 1–2 Minuten) …"
pyinstaller \
  --windowed \
  --noconfirm \
  --clean \
  --name "Rezept Transcripts" \
  native_app.py

echo ""
echo "📦  ZIP erstellen …"
cd dist
rm -f Rezept_Transcripts.zip
zip -r --quiet Rezept_Transcripts.zip "Rezept Transcripts.app"
cd ..

echo ""
echo "✅  Fertig!"
echo ""
echo "   Die fertige App liegt hier:"
echo "   $(pwd)/dist/Rezept_Transcripts.zip"
echo ""
echo "   Einfach per AirDrop, iCloud oder E-Mail an deine Frau schicken."
echo "   Sie muss nur entpacken und in den Programme-Ordner ziehen — fertig."
echo ""
