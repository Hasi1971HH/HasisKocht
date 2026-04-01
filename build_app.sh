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
pip3 install --quiet pyinstaller youtube-transcript-api groq

echo ""
echo "🏗️   App bauen (dauert 1–2 Minuten) …"
pyinstaller \
  --windowed \
  --noconfirm \
  --clean \
  --name "HasisKocht" \
  --hidden-import groq \
  --hidden-import httpx \
  --hidden-import httpcore \
  --hidden-import anyio \
  --hidden-import distro \
  --hidden-import sniffio \
  native_app.py

echo ""
echo "📦  ZIP erstellen …"
cd dist
rm -f HasisKocht.zip
zip -r --quiet HasisKocht.zip "HasisKocht.app"
cd ..

echo ""
echo "✅  Fertig!"
echo ""
echo "   Die fertige App liegt hier:"
echo "   $(pwd)/dist/HasisKocht.zip"
echo ""
echo "   ZIP entpacken → HasisKocht.app in den Programme-Ordner ziehen → fertig."
echo "   Beim ersten Start wird einmalig der Groq API Key abgefragt."
echo ""
