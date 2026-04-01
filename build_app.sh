#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# build_app.sh — Baut HasisKocht als Mac-App + DMG
#
# Voraussetzung: Python 3 + Homebrew (nur einmalig als Entwickler nötig)
# Aufruf:  bash build_app.sh
#
# Ergebnis: dist/HasisKocht.dmg  → direkt weiterschicken oder anbieten
# ─────────────────────────────────────────────────────────────────────────────
set -e

APP_NAME="HasisKocht"

echo ""
echo "🔧  Abhängigkeiten installieren …"
pip3 install --quiet pyinstaller youtube-transcript-api groq

echo ""
echo "🏗️   App bauen (dauert 1–2 Minuten) …"
pyinstaller \
  --windowed \
  --noconfirm \
  --clean \
  --name "$APP_NAME" \
  --hidden-import groq \
  --hidden-import httpx \
  --hidden-import httpcore \
  --hidden-import anyio \
  --hidden-import distro \
  --hidden-import sniffio \
  native_app.py

echo ""
echo "💿  DMG erstellen …"

DMG_DIR="dist/dmg_tmp"
rm -rf "$DMG_DIR"
mkdir -p "$DMG_DIR"

# App + Applications-Symlink ins DMG-Verzeichnis
cp -r "dist/$APP_NAME.app" "$DMG_DIR/"
ln -s /Applications "$DMG_DIR/Applications"

# DMG bauen
hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$DMG_DIR" \
  -ov \
  -format UDZO \
  "dist/$APP_NAME.dmg"

# Aufräumen
rm -rf "$DMG_DIR"

echo ""
echo "✅  Fertig!"
echo ""
echo "   Die fertige App liegt hier:"
echo "   $(pwd)/dist/$APP_NAME.dmg"
echo ""
echo "   Einfach per AirDrop, iCloud oder E-Mail teilen."
echo "   Empfänger: DMG öffnen → App in Programme ziehen → starten."
echo "   Beim ersten Start wird einmalig der kostenlose Groq API Key abgefragt."
echo "   Key erstellen: console.groq.com"
echo ""
