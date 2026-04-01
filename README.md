# 🍳 HasisKocht

**YouTube-Kochvideo → Interaktives HTML-Rezept — vollautomatisch, per KI.**

Einfach eine YouTube-URL eingeben. Die App lädt das Transkript, schickt es an eine KI und öffnet ein fertig aufbereitetes Rezept im Browser — mit Einkaufsliste, Personen-Slider und Nährwerten.

---

## ✨ Features

- **Einkaufsliste** mit Checkboxen zum Abhaken
- **Personen-Slider** (1–6): alle Mengenangaben passen sich dynamisch an
- **Zubereitung** mit nummerierten Schritten und ausführlichen Beschreibungen
- **Nährwerte** pro Portion — Kohlenhydrate pro 100 g und pro Portion hervorgehoben
- **Video-Link** direkt in der App
- Alle Maßeinheiten metrisch (g, ml, kg, l)
- Apple-Design — hell, sauber, einfach
- Rezepte werden lokal gespeichert (`~/Documents/Rezept-Transcripts/`)

---

## 📸 So sieht's aus

| Zutaten | Zubereitung |
|---|---|
| *(Screenshot einfügen)* | *(Screenshot einfügen)* |

---

## 🚀 Installation (fertige App)

### Voraussetzung
- Mac (Apple Silicon oder Intel)
- Kostenloser [Groq API Key](#-groq-api-key-einrichten) (30 Sekunden)

### App installieren
1. **[⬇️ HasisKocht.dmg herunterladen](../../releases/latest)**
2. DMG öffnen
3. `HasisKocht.app` in den **Programme**-Ordner ziehen
4. App starten → beim ersten Start Groq API Key eingeben → fertig

---

## 🔑 Groq API Key einrichten

Der Key ist kostenlos und dauert 30 Sekunden:

1. Geh auf **[console.groq.com](https://console.groq.com)**
2. Konto erstellen (kostenlos, keine Kreditkarte nötig)
3. Links auf **"API Keys"** → **"Create API Key"**
4. Key kopieren
5. In HasisKocht: beim ersten Start automatisch abgefragt — oder jederzeit über **⚙** oben rechts ändern

> Der Key wird ausschließlich lokal auf deinem Mac gespeichert (`~/.hasiskocht_config`).

---

## 🛠️ App selbst bauen (für Entwickler)

### Voraussetzungen
- Python 3.11+
- Homebrew

### Setup
```bash
git clone https://github.com/Hasi1971HH/Hasis-AI-Rezepte.git
cd Hasis-AI-Rezepte
python3 -m venv venv
source venv/bin/activate
pip install youtube-transcript-api groq
```

### App + DMG bauen
```bash
bash build_app.sh
```

Ergebnis: `dist/HasisKocht.dmg` — fertig zum Teilen.

### Nur testen (ohne Build)
```bash
source venv/bin/activate
python3 native_app.py
```

---

## 📁 Projektstruktur

```
native_app.py      — Haupt-App (Tkinter, Groq-Integration, HTML-Generator)
build_app.sh       — Baut .app + DMG mit PyInstaller
requirements.txt   — Python-Abhängigkeiten
setup_native.py    — py2app-Konfiguration (Alternative zu PyInstaller)
```

---

## 🤖 Verwendete KI

- **Modell:** `llama-3.3-70b-versatile` via [Groq](https://groq.com)
- **Was die KI macht:** Rezeptdaten aus dem Transkript als JSON extrahieren
- **Was Python macht:** Daraus das vollständige interaktive HTML bauen

---

## 📄 Lizenz

MIT — mach damit was du willst.
