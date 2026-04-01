"""
HasisKocht — Native macOS App
YouTube-URL eingeben → Transcript laden → Groq extrahiert JSON → Python baut HTML-Rezept → Browser öffnet sich.
"""
import json
import os
import re
import subprocess
import threading
import webbrowser
import urllib.request
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from youtube_transcript_api import (
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

PREFERRED_LANGUAGES = ["de", "en", "fr", "es", "it"]
TRANSCRIPTS_DIR = Path.home() / "Documents" / "Rezept-Transcripts"
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = Path.home() / ".hasiskocht_config"

# ── Groq-Prompt: nur JSON extrahieren (wenige Tokens) ─────────────────────────
JSON_PROMPT = """Du extrahierst Rezeptdaten aus einem YouTube-Transkript und gibst NUR valides JSON zurück.
Kein erklärender Text, kein Markdown, nur das JSON-Objekt.

Pflichtfelder:
{
  "titel": "Name des Gerichts",
  "kurzbeschreibung": "Ein Satz über das Gericht.",
  "portionen_basis": 4,
  "zutaten": [
    {
      "gruppe": "Abschnittsname (z.B. Gewürzmischung, Sofrito, Topping — oder leer wenn keine Gruppen)",
      "name": "Zutat",
      "menge": 200,
      "einheit": "g",
      "notiz": "kurzer Hinweis zur Vorbereitung oder Verwendung (optional, sonst leer)"
    }
  ],
  "zubereitung": [
    {
      "titel": "Kurze Schritt-Überschrift (5-8 Wörter)",
      "beschreibung": "Ausführliche Anleitung mit Zeiten, Temperaturen und Tipps aus dem Video."
    }
  ],
  "naehrwerte_pro_portion": {
    "kalorien": 400,
    "kohlenhydrate_g": 45,
    "davon_zucker_g": 5,
    "eiweiss_g": 20,
    "fett_g": 12,
    "ballaststoffe_g": 4
  },
  "naehrwerte_pro_100g": {
    "kalorien": 130,
    "kohlenhydrate_g": 15
  },
  "video_id": "YouTubeVideoID"
}

Alle Mengenangaben zwingend metrisch (g, ml, kg, l). Niemals oz, cup, pound.
Zubereitung so detailliert wie möglich — alle Hinweise, Zeiten und Tipps aus dem Video einfließen lassen."""


# ── Farben & Stil ──────────────────────────────────────────────────────────────
BG        = "#f5f5f7"
FG        = "#1d1d1f"
RED       = "#cc0000"
GREEN     = "#1a7f37"
CARD_BG   = "#ffffff"
BORDER    = "#d2d2d7"
BTN_BG    = "#cc0000"
BTN_FG    = "#ffffff"
BTN_HOVER = "#a30000"
MUTED     = "#6e6e73"
BLUE      = "#0071e3"


# ── Config / API Key ───────────────────────────────────────────────────────────
def load_api_key() -> str:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text()).get("groq_api_key", "")
        except Exception:
            pass
    return ""


def save_api_key(key: str):
    CONFIG_FILE.write_text(json.dumps({"groq_api_key": key.strip()}))


# ── Groq: Transkript → JSON ────────────────────────────────────────────────────
def strip_timestamps(transcript: str) -> str:
    return re.sub(r'^\[\d{2}:\d{2}\] ?', '', transcript, flags=re.MULTILINE)


def extract_recipe_json(full_transcript: str) -> dict:
    from groq import Groq
    client = Groq(api_key=load_api_key())
    clean = strip_timestamps(full_transcript)
    if len(clean) > 10000:
        clean = clean[:10000]
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": JSON_PROMPT},
            {"role": "user", "content": f"Transkript:\n\n{clean}"},
        ],
        max_tokens=2000,
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    # JSON aus Markdown-Codeblöcken befreien falls nötig
    raw = re.sub(r'^```(?:json)?\n?', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\n?```$', '', raw)
    return json.loads(raw)


# ── Python: JSON → vollständiges HTML ─────────────────────────────────────────
def build_html(data: dict) -> str:
    titel        = data.get("titel", "Rezept")
    kurz         = data.get("kurzbeschreibung", "")
    portionen    = int(data.get("portionen_basis", 4))
    video_id     = data.get("video_id", "")
    zutaten      = data.get("zutaten", [])
    zubereitung  = data.get("zubereitung", [])
    nw_portion   = data.get("naehrwerte_pro_portion", {})
    nw_100g      = data.get("naehrwerte_pro_100g", {})

    # Zutaten-Zeilen als JSON für den Slider-JS
    zutaten_json = json.dumps(zutaten, ensure_ascii=False)

    # Zubereitung: unterstützt {titel, beschreibung} und legacy string
    def render_step(s):
        def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if isinstance(s, dict):
            titel_s = esc(s.get("titel", ""))
            desc_s  = esc(s.get("beschreibung", ""))
            return (f'<li class="step"><span class="step-titel">{titel_s}</span>'
                    f'<span class="step-desc">{desc_s}</span></li>')
        return f'<li class="step"><span class="step-desc">{esc(str(s))}</span></li>'

    zubereitung_html = "\n".join(render_step(s) for s in zubereitung)

    # Zutaten nach Gruppe sortieren für statisches Gruppen-HTML (für Notizen)
    gruppen_html_parts = []
    current_gruppe = None
    for z in zutaten:
        g = z.get("gruppe", "")
        if g and g != current_gruppe:
            current_gruppe = g
            gruppen_html_parts.append(f'<div class="gruppe-header">{g}</div>')
        notiz = z.get("notiz", "")
        notiz_html = f'<span class="zutat-notiz">{notiz}</span>' if notiz else ""
        gruppen_html_parts.append(
            f'<label class="zutat-row">'
            f'<input type="checkbox" class="zutat-check">'
            f'<span class="zutat-info"><span class="zutat-name">{z.get("name","")}</span>'
            f'{notiz_html}</span>'
            f'<span class="zutat-menge" data-base="{z.get("menge",0)}" '
            f'data-einheit="{z.get("einheit","")}">'
            f'{z.get("menge",0)} {z.get("einheit","")}</span></label>'
        )
    gruppen_html = "\n".join(gruppen_html_parts)

    def nw_row(label, key, unit, highlight=False):
        val = nw_portion.get(key, "–")
        v100 = nw_100g.get(key, "–")
        cls = ' class="kh-row"' if highlight else ""
        return f'<tr{cls}><td>{label}</td><td><b>{val} {unit}</b></td><td>{v100} {unit}</td></tr>'

    nw_rows = (
        nw_row("Kalorien", "kalorien", "kcal") +
        nw_row("Kohlenhydrate", "kohlenhydrate_g", "g", highlight=True) +
        nw_row("– davon Zucker", "davon_zucker_g", "g") +
        nw_row("Eiweiß", "eiweiss_g", "g") +
        nw_row("Fett", "fett_g", "g") +
        nw_row("Ballaststoffe", "ballaststoffe_g", "g")
    )

    yt_link = ""
    if video_id:
        yt_link = f'''
        <div class="yt-link-box">
          <a href="https://www.youtube.com/watch?v={video_id}" target="_blank" class="yt-link">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="#ff0000">
              <path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.6A3 3 0 0 0 .5 6.2C0 8.1 0 12 0 12s0 3.9.5 5.8a3 3 0 0 0 2.1 2.1c1.9.6 9.4.6 9.4.6s7.5 0 9.4-.6a3 3 0 0 0 2.1-2.1C24 15.9 24 12 24 12s0-3.9-.5-5.8z"/>
              <path d="M9.75 15.5l6.25-3.5-6.25-3.5v7z" fill="white"/>
            </svg>
            <span>Auf YouTube ansehen</span>
          </a>
        </div>'''

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titel}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
         background: #f5f5f7; color: #1d1d1f; min-height: 100vh; }}
  .card {{ max-width: 680px; margin: 40px auto; background: #fff;
           border-radius: 18px; box-shadow: 0 4px 24px rgba(0,0,0,.08);
           overflow: hidden; }}
  .header {{ background: #fff; padding: 32px 32px 0; }}
  h1 {{ font-size: 28px; font-weight: 700; letter-spacing: -.5px; }}
  .kurz {{ color: #6e6e73; margin-top: 6px; font-size: 15px; }}
  .slider-box {{ padding: 20px 32px; background: #f5f5f7;
                 margin: 20px 0 0; display: flex; align-items: center; gap: 16px; }}
  .slider-box label {{ font-size: 14px; color: #6e6e73; white-space: nowrap; }}
  .slider-box input[type=range] {{ flex: 1; accent-color: #cc0000; }}
  .slider-box .portions-num {{ font-size: 20px; font-weight: 700;
                                min-width: 28px; text-align: center; }}
  .tabs {{ display: flex; border-bottom: 1px solid #e5e5ea; padding: 0 32px; }}
  .tab {{ padding: 14px 18px; font-size: 14px; font-weight: 500; color: #6e6e73;
          cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; }}
  .tab.active {{ color: #cc0000; border-bottom-color: #cc0000; }}
  .panel {{ display: none; padding: 28px 32px 36px; }}
  .panel.active {{ display: block; }}
  /* Zutaten */
  .gruppe-header {{ font-size: 13px; font-weight: 700; color: #6e6e73; text-transform: uppercase;
                    letter-spacing: .5px; padding: 18px 0 6px; }}
  .gruppe-header:first-child {{ padding-top: 0; }}
  .zutat-row {{ display: flex; align-items: flex-start; gap: 12px;
               padding: 10px 0; border-bottom: 1px solid #f0f0f5; font-size: 15px;
               cursor: pointer; }}
  .zutat-row .zutat-info {{ flex: 1; }}
  .zutat-check {{ appearance: none; -webkit-appearance: none; width: 20px; height: 20px;
                  border: 2px solid #d2d2d7; border-radius: 6px; cursor: pointer;
                  flex-shrink: 0; margin-top: 1px; transition: all .15s; }}
  .zutat-check:checked {{ background: #cc0000; border-color: #cc0000;
                          background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 12 10' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 5l3.5 3.5L11 1' stroke='white' stroke-width='2' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
                          background-repeat: no-repeat; background-position: center; background-size: 70%%; }}
  .zutat-row:has(.zutat-check:checked) .zutat-name {{ text-decoration: line-through; color: #6e6e73; }}
  .zutat-row:has(.zutat-check:checked) .zutat-menge {{ color: #6e6e73; }}
  .zutat-row:last-child {{ border-bottom: none; }}
  .zutat-info {{ display: flex; flex-direction: column; gap: 2px; }}
  .zutat-name {{ color: #1d1d1f; }}
  .zutat-notiz {{ font-size: 12px; color: #6e6e73; font-style: italic; }}
  .zutat-menge {{ font-weight: 600; color: #1d1d1f; min-width: 80px; text-align: right;
                  white-space: nowrap; padding-left: 12px; }}
  /* Zubereitung */
  ol.steps {{ padding-left: 0; list-style: none; counter-reset: step; }}
  li.step {{ counter-increment: step; padding: 14px 0 14px 48px; position: relative;
             border-bottom: 1px solid #f0f0f5; }}
  li.step:last-child {{ border-bottom: none; }}
  li.step::before {{ content: counter(step); position: absolute; left: 0; top: 14px;
                     width: 30px; height: 30px; background: #cc0000; color: #fff;
                     border-radius: 50%; display: flex; align-items: center;
                     justify-content: center; font-weight: 700; font-size: 13px; }}
  .step-titel {{ display: block; font-weight: 600; font-size: 15px; color: #1d1d1f;
                 margin-bottom: 4px; }}
  .step-desc {{ display: block; font-size: 14px; color: #3d3d3f; line-height: 1.6; }}
  /* Nährwerte */
  .nw-table {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
  .nw-table th {{ text-align: left; padding: 10px 0; color: #6e6e73;
                  font-weight: 500; border-bottom: 1px solid #e5e5ea; font-size: 13px; }}
  .nw-table td {{ padding: 11px 0; border-bottom: 1px solid #f0f0f5; }}
  .nw-table td:not(:first-child) {{ text-align: right; }}
  .nw-table tr:last-child td {{ border-bottom: none; }}
  tr.kh-row {{ background: #fff8f0; }}
  tr.kh-row td {{ padding: 13px 8px; border-radius: 8px; }}
  tr.kh-row td:first-child {{ padding-left: 12px; border-radius: 8px 0 0 8px; }}
  tr.kh-row td:last-child {{ border-radius: 0 8px 8px 0; padding-right: 12px; }}
  tr.kh-row b {{ color: #cc0000; font-size: 16px; }}
  .kh-label {{ font-size: 11px; color: #6e6e73; margin-top: 4px; }}
  /* Video */
  .yt-link-box {{ text-align: center; padding: 32px 0; }}
  .yt-link {{ display: inline-flex; align-items: center; gap: 14px; text-decoration: none;
              background: #fff; border: 1px solid #e5e5ea; border-radius: 14px;
              padding: 20px 32px; transition: box-shadow .2s; }}
  .yt-link:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,.1); }}
  .yt-link span {{ font-size: 17px; font-weight: 600; color: #1d1d1f; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>{titel}</h1>
    <p class="kurz">{kurz}</p>
  </div>

  <div class="slider-box">
    <label>Portionen</label>
    <input type="range" min="1" max="6" value="{portionen}" id="slider"
           oninput="updatePortions(this.value)">
    <span class="portions-num" id="portionsNum">{portionen}</span>
  </div>

  <div class="tabs">
    <div class="tab active" onclick="showTab('zutaten',this)">Zutaten</div>
    <div class="tab" onclick="showTab('zubereitung',this)">Zubereitung</div>
    <div class="tab" onclick="showTab('naehrwerte',this)">Nährwerte</div>
    <div class="tab" onclick="showTab('video',this)">Video</div>
  </div>

  <div id="zutaten" class="panel active">
    {gruppen_html}
  </div>

  <div id="zubereitung" class="panel">
    <ol class="steps">{zubereitung_html}</ol>
  </div>

  <div id="naehrwerte" class="panel">
    <table class="nw-table">
      <thead><tr>
        <th>Nährwert</th>
        <th>Pro Portion</th>
        <th>Pro 100 g</th>
      </tr></thead>
      <tbody>{nw_rows}</tbody>
    </table>
    <p class="kh-label" style="margin-top:12px">
      * Kohlenhydrate rot hervorgehoben — Werte sind Schätzungen.
    </p>
  </div>

  <div id="video" class="panel">
    {yt_link if yt_link else '<p style="color:#6e6e73">Keine Video-ID gefunden.</p>'}
  </div>
</div>

<script>
const BASIS = {portionen};

function showTab(id, el) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
}}

function updatePortions(val) {{
  document.getElementById('portionsNum').textContent = val;
  const faktor = val / BASIS;
  document.querySelectorAll('.zutat-menge').forEach(el => {{
    const base = parseFloat(el.dataset.base);
    const einheit = el.dataset.einheit;
    const neu = base * faktor;
    const anzeige = (neu % 1 === 0) ? neu : neu.toFixed(1);
    el.textContent = anzeige + ' ' + einheit;
  }});
}}
</script>
</body>
</html>"""


# ── Hilfs-Funktionen ───────────────────────────────────────────────────────────
def extract_video_id(url: str) -> str | None:
    for pattern in [r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", r"(?:embed/)([A-Za-z0-9_-]{11})"]:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def fetch_video_title(video_id: str) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        for pat in [r'<title>(.+?)\s*-\s*YouTube</title>',
                    r'property="og:title"\s+content="([^"]+)"']:
            m = re.search(pat, html)
            if m:
                return m.group(1).strip()
    except Exception:
        pass
    return video_id


def slugify(title: str) -> str:
    title = title.replace("&amp;", "&").replace("&#39;", "'")
    title = re.sub(r'[^\w\s\-äöüÄÖÜß]', '', title)
    return re.sub(r'\s+', '_', title.strip())[:80]


def fetch_transcript(video_id: str) -> tuple[str, str]:
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)
    try:
        transcript = transcript_list.find_manually_created_transcript(PREFERRED_LANGUAGES)
    except NoTranscriptFound:
        transcript = transcript_list.find_generated_transcript(PREFERRED_LANGUAGES)
    fetched = transcript.fetch()
    lang = transcript.language_code
    lines = []
    for snippet in fetched:
        start = snippet.start
        lines.append(f"[{int(start//60):02d}:{int(start%60):02d}] {snippet.text.strip()}")
    return "\n".join(lines), lang


# ── API Key Dialog ─────────────────────────────────────────────────────────────
class ApiKeyDialog(tk.Toplevel):
    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self._on_save = on_save
        self.title("Groq API Key")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.grab_set()
        w, h = 460, 250
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        f_title = tkfont.Font(family="SF Pro Display", size=16, weight="bold")
        f_text  = tkfont.Font(family="SF Pro Text", size=12)
        f_small = tkfont.Font(family="SF Pro Text", size=11)
        f_btn   = tkfont.Font(family="SF Pro Text", size=13, weight="bold")

        tk.Label(self, text="Groq API Key", font=f_title, bg=BG, fg=FG).pack(anchor="w", padx=24, pady=(24,4))
        tk.Label(self, text="Kostenlosen Key unter console.groq.com erstellen.",
                 font=f_small, bg=BG, fg=MUTED).pack(anchor="w", padx=24)
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=24, pady=14)

        ef = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1, bd=0)
        ef.pack(fill="x", padx=24)
        self._key_var = tk.StringVar(value=load_api_key())
        entry = tk.Entry(ef, textvariable=self._key_var, font=f_text, bd=0, relief="flat",
                         bg=CARD_BG, fg=FG, insertbackground=FG, show="•", highlightthickness=0)
        entry.pack(fill="x", padx=10, pady=9)
        entry.bind("<Return>", lambda _: self._save())
        entry.focus_set()

        bf = tk.Frame(self, bg=BLUE, cursor="hand2")
        bf.pack(fill="x", padx=24, pady=(14,0))
        bl = tk.Label(bf, text="Speichern", font=f_btn, bg=BLUE, fg="#ffffff", pady=10, cursor="hand2")
        bl.pack(fill="x")
        for w in (bf, bl):
            w.bind("<Button-1>", lambda _: self._save())

    def _save(self):
        key = self._key_var.get().strip()
        if key:
            save_api_key(key)
            if self._on_save:
                self._on_save()
            self.destroy()


# ── Haupt-App ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HasisKocht")
        self.resizable(False, False)
        self.configure(bg=BG)
        w, h = 520, 420
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        self._f_title  = tkfont.Font(family="SF Pro Display", size=20, weight="bold")
        self._f_label  = tkfont.Font(family="SF Pro Text", size=13)
        self._f_small  = tkfont.Font(family="SF Pro Text", size=11)
        self._f_btn    = tkfont.Font(family="SF Pro Text", size=13, weight="bold")
        self._f_status = tkfont.Font(family="SF Pro Text", size=12)

        self._build_ui()
        if not load_api_key():
            self.after(300, self._show_key_dialog)

    def _show_key_dialog(self):
        ApiKeyDialog(self)

    def _build_ui(self):
        pad = dict(padx=28, pady=0)

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=28, pady=(32,2))
        tk.Label(header, text="HasisKocht", font=self._f_title, bg=BG, fg=FG).pack(side="left")
        sl = tk.Label(header, text="⚙", font=tkfont.Font(size=18), bg=BG, fg=MUTED, cursor="hand2")
        sl.pack(side="right")
        sl.bind("<Button-1>", lambda _: self._show_key_dialog())

        tk.Label(self, text="YouTube-Video → Interaktives HTML-Rezept",
                 font=self._f_small, bg=BG, fg=MUTED).pack(anchor="w", **pad)
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=28, pady=18)
        tk.Label(self, text="YouTube-URL", font=self._f_label, bg=BG, fg=FG).pack(anchor="w", **pad)

        ef = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1, bd=0)
        ef.pack(fill="x", padx=28, pady=(6,0))
        self._url_var = tk.StringVar()
        self._entry = tk.Entry(ef, textvariable=self._url_var, font=self._f_label,
                               bd=0, relief="flat", bg=CARD_BG, fg=FG,
                               insertbackground=FG, highlightthickness=0)
        self._entry.pack(fill="x", padx=10, pady=9)
        self._entry.bind("<Return>", lambda _: self._start_download())
        self._entry.bind("<FocusIn>",  lambda e: (ef.config(highlightbackground=BLUE, highlightthickness=2), self._on_focus_in(e)))
        self._entry.bind("<FocusOut>", lambda e: (ef.config(highlightbackground=BORDER, highlightthickness=1), self._on_focus_out(e)))

        self._placeholder = "https://www.youtube.com/watch?v=..."
        self._entry.insert(0, self._placeholder)
        self._entry.config(fg=MUTED)

        pb = tk.Label(ef, text="Einfügen", font=self._f_small, bg=CARD_BG, fg=RED, cursor="hand2")
        pb.place(relx=1.0, rely=0.5, anchor="e", x=-10)
        pb.bind("<Button-1>", self._paste_url)

        self._btn_frame = tk.Frame(self, bg=BTN_BG, cursor="hand2")
        self._btn_frame.pack(fill="x", padx=28, pady=(16,0))
        self._btn_lbl = tk.Label(self._btn_frame, text="Rezept erstellen",
                                  font=self._f_btn, bg=BTN_BG, fg=BTN_FG, cursor="hand2", pady=11)
        self._btn_lbl.pack(fill="x")
        self._btn_enabled = True
        for w in (self._btn_frame, self._btn_lbl):
            w.bind("<Button-1>", lambda _: self._start_download() if self._btn_enabled else None)
            w.bind("<Enter>", lambda _: self._set_btn_color(BTN_HOVER))
            w.bind("<Leave>", lambda _: self._set_btn_color(BTN_BG))

        self._status_frame = tk.Frame(self, bg=BG)
        self._status_frame.pack(fill="x", padx=28, pady=(18,0))
        self._status_icon = tk.Label(self._status_frame, text="", font=self._f_status, bg=BG)
        self._status_icon.pack(side="left")
        self._status_lbl = tk.Label(self._status_frame, text="", font=self._f_status,
                                     bg=BG, fg=FG, wraplength=440, justify="left")
        self._status_lbl.pack(side="left", padx=(6,0))

        fl = tk.Label(self, text="Dateien: Dokumente → Rezept-Transcripts",
                      font=self._f_small, bg=BG, fg=MUTED, cursor="hand2")
        fl.pack(anchor="w", padx=28, pady=(20,0))
        fl.bind("<Button-1>", self._open_folder)

    def _set_btn_color(self, color):
        self._btn_frame.config(bg=color)
        self._btn_lbl.config(bg=color)

    def _set_btn_enabled(self, enabled: bool):
        self._btn_enabled = enabled
        self._set_btn_color("#e89090" if not enabled else BTN_BG)
        self._btn_lbl.config(fg=BTN_FG)

    def _on_focus_in(self, _e):
        if self._entry.get() == self._placeholder:
            self._entry.delete(0, "end")
            self._entry.config(fg=FG)

    def _on_focus_out(self, _e):
        if not self._entry.get():
            self._entry.insert(0, self._placeholder)
            self._entry.config(fg=MUTED)

    def _paste_url(self, _e=None):
        try:
            text = self.clipboard_get()
            self._entry.delete(0, "end")
            self._entry.config(fg=FG)
            self._entry.insert(0, text.strip())
        except tk.TclError:
            pass

    def _open_folder(self, _e=None):
        subprocess.Popen(["open", str(TRANSCRIPTS_DIR)])

    def _set_status(self, kind: str, message: str):
        icons  = {"ok": "✅", "error": "⚠️", "loading": "⏳", "generating": "🤖"}
        colors = {"ok": GREEN, "error": RED, "loading": FG, "generating": FG}
        self._status_icon.config(text=icons.get(kind, ""))
        self._status_lbl.config(text=message, fg=colors.get(kind, FG))

    def _start_download(self):
        if not load_api_key():
            self._show_key_dialog()
            return
        url = self._url_var.get().strip()
        if not url or url == self._placeholder:
            self._set_status("error", "Bitte eine YouTube-URL eingeben.")
            return
        video_id = extract_video_id(url)
        if not video_id:
            self._set_status("error", "Ungültige YouTube-URL. Bitte überprüfe den Link.")
            return
        self._set_btn_enabled(False)
        self._set_status("loading", "Transcript wird geladen …")
        threading.Thread(target=self._download, args=(video_id,), daemon=True).start()

    def _download(self, video_id: str):
        try:
            transcript_text, lang = fetch_transcript(video_id)
        except TranscriptsDisabled:
            self.after(0, self._set_status, "error", "Für dieses Video sind Untertitel deaktiviert.")
            self.after(0, self._set_btn_enabled, True)
            return
        except NoTranscriptFound:
            self.after(0, self._set_status, "error", "Kein Transcript für dieses Video gefunden.")
            self.after(0, self._set_btn_enabled, True)
            return
        except (RequestBlocked, IpBlocked):
            self.after(0, self._set_status, "error", "YouTube blockiert die Anfrage.")
            self.after(0, self._set_btn_enabled, True)
            return
        except Exception as e:
            self.after(0, self._set_status, "error", f"Fehler: {e}")
            self.after(0, self._set_btn_enabled, True)
            return

        title = fetch_video_title(video_id)
        slug  = slugify(title)

        full_transcript = (
            f"YouTube Transcript: {title}\nVideo-ID: {video_id}\n"
            f"URL: https://www.youtube.com/watch?v={video_id}\nSprache: {lang}\n"
            + "=" * 60 + "\n\n" + transcript_text
        )
        (TRANSCRIPTS_DIR / f"{slug}_{lang}.txt").write_text(full_transcript, encoding="utf-8")

        self.after(0, self._set_status, "generating", "Rezept wird generiert …")
        try:
            recipe_data = extract_recipe_json(full_transcript)
            html_content = build_html(recipe_data)
        except json.JSONDecodeError as e:
            self.after(0, self._set_status, "error", f"KI-Antwort kein gültiges JSON: {e}")
            self.after(0, self._set_btn_enabled, True)
            return
        except Exception as e:
            err = str(e)
            if any(k in err.lower() for k in ("auth", "api_key", "invalid_api", "unauthorized")):
                self.after(0, self._set_status, "error", "Ungültiger API Key. Bitte über ⚙ ändern.")
            else:
                self.after(0, self._set_status, "error", f"Fehler: {err[:120]}")
            self.after(0, self._set_btn_enabled, True)
            return

        html_path = TRANSCRIPTS_DIR / f"{slug}.html"
        html_path.write_text(html_content, encoding="utf-8")

        self.after(0, self._set_status, "ok", "Fertig! Rezept öffnet sich im Browser.")
        self.after(0, self._set_btn_enabled, True)
        self.after(0, lambda: webbrowser.open(html_path.as_uri()))


if __name__ == "__main__":
    app = App()
    app.mainloop()
