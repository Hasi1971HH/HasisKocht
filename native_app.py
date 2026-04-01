"""
HasisKocht — Native macOS App
YouTube-URL eingeben → Transcript laden → Groq KI generiert HTML-Rezept → Browser öffnet sich.
Tkinter-basiert, kein Flask, kein Browser-Start nötig.
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

SYSTEM_PROMPT = """Du bist ein Koch-Assistent. Wenn du ein YouTube-Transkript erhältst, erstelle daraus ein vollständiges, interaktives HTML-Rezept mit folgenden Anforderungen:

- Helles Design wie von Apple (weiß, hellgrau, saubere Typografie, System-Font)
- Alle Inhalte auf Deutsch
- Interaktiver Regler (Slider) um die Portionsanzahl von 1–6 Personen zu wählen – alle Mengenangaben passen sich dynamisch an
- Navigation via Tabs: Zutaten, Zubereitung, Nährwerte, Video
- Tab „Nährwerte": Alle Werte pro Portion anzeigen. Kohlenhydrate sowohl pro 100g als auch pro 1 Portion in einem farblich hervorgehobenen Block darstellen.
- Tab „Video": Die YouTube-Video-ID aus dem Transkript auslesen und als großen, fett formatierten Link mit YouTube-Logo darstellen (kein eingebettetes Video, nur ein klickbarer Link)
- Alle Maßeinheiten zwingend metrisch (g, ml, kg, l) – niemals oz, cup, stone, pound oder andere imperiale Einheiten. Dies hat oberste Priorität.
- Das HTML muss vollständig in sich geschlossen sein (kein externes CSS/JS, alles inline)

Antworte AUSSCHLIESSLICH mit dem vollständigen HTML-Code. Keine Erklärungen, kein Markdown, kein Text davor oder danach. Beginne direkt mit <!DOCTYPE html>."""


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


# ── Rezept-Generierung via Groq ────────────────────────────────────────────────
def strip_timestamps(transcript: str) -> str:
    """Entfernt [MM:SS]-Zeitstempel um Tokens zu sparen."""
    return re.sub(r'^\[\d{2}:\d{2}\] ?', '', transcript, flags=re.MULTILINE)


def generate_recipe_html(full_transcript: str) -> str:
    from groq import Groq
    client = Groq(api_key=load_api_key())
    clean_transcript = strip_timestamps(full_transcript)
    # Auf 5.000 Zeichen begrenzen — hält Input+Output unter Groq Free-Tier-Limit
    if len(clean_transcript) > 5000:
        clean_transcript = clean_transcript[:5000]
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Hier ist das YouTube-Transkript:\n\n{clean_transcript}"},
        ],
        max_tokens=3000,
        temperature=0.3,
    )
    html = response.choices[0].message.content.strip()
    # Markdown-Codeblöcke entfernen, falls das Modell sie trotzdem ausgibt
    html = re.sub(r'^```(?:html)?\n?', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\n?```$', '', html)
    return html


# ── Hilfs-Funktionen ───────────────────────────────────────────────────────────
def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def fetch_video_title(video_id: str) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    req = urllib.request.Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        m = re.search(r'<title>(.+?)\s*-\s*YouTube</title>', html)
        if m:
            return m.group(1).strip()
        m = re.search(r'property="og:title"\s+content="([^"]+)"', html)
        if m:
            return m.group(1).strip()
        m = re.search(r'"title"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"([^"]+)"', html)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return video_id


def slugify(title: str) -> str:
    title = title.replace("&amp;", "&").replace("&#39;", "'")
    title = re.sub(r'[^\w\s\-äöüÄÖÜß]', '', title)
    title = re.sub(r'\s+', '_', title.strip())
    return title[:80]


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
        text = snippet.text.strip()
        start = snippet.start
        minutes = int(start // 60)
        seconds = int(start % 60)
        lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
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
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        f_title = tkfont.Font(family="SF Pro Display", size=16, weight="bold")
        f_text  = tkfont.Font(family="SF Pro Text",    size=12)
        f_small = tkfont.Font(family="SF Pro Text",    size=11)
        f_btn   = tkfont.Font(family="SF Pro Text",    size=13, weight="bold")

        tk.Label(self, text="Groq API Key",
                 font=f_title, bg=BG, fg=FG).pack(anchor="w", padx=24, pady=(24, 4))
        tk.Label(self, text="Kostenlosen Key unter console.groq.com erstellen.",
                 font=f_small, bg=BG, fg=MUTED).pack(anchor="w", padx=24)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=24, pady=14)

        entry_frame = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER,
                               highlightthickness=1, bd=0)
        entry_frame.pack(fill="x", padx=24)

        self._key_var = tk.StringVar(value=load_api_key())
        entry = tk.Entry(entry_frame, textvariable=self._key_var,
                         font=f_text, bd=0, relief="flat",
                         bg=CARD_BG, fg=FG, insertbackground=FG,
                         show="•", highlightthickness=0)
        entry.pack(fill="x", padx=10, pady=9)
        entry.bind("<Return>", lambda _: self._save())
        entry.focus_set()

        btn_frame = tk.Frame(self, bg=BLUE, cursor="hand2")
        btn_frame.pack(fill="x", padx=24, pady=(14, 0))
        btn_lbl = tk.Label(btn_frame, text="Speichern",
                           font=f_btn, bg=BLUE, fg="#ffffff", pady=10, cursor="hand2")
        btn_lbl.pack(fill="x")
        for widget in (btn_frame, btn_lbl):
            widget.bind("<Button-1>", lambda _: self._save())

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
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self._f_title  = tkfont.Font(family="SF Pro Display", size=20, weight="bold")
        self._f_label  = tkfont.Font(family="SF Pro Text",    size=13)
        self._f_small  = tkfont.Font(family="SF Pro Text",    size=11)
        self._f_btn    = tkfont.Font(family="SF Pro Text",    size=13, weight="bold")
        self._f_status = tkfont.Font(family="SF Pro Text",    size=12)

        self._build_ui()

        if not load_api_key():
            self.after(300, self._show_key_dialog)

    def _show_key_dialog(self):
        ApiKeyDialog(self)

    # ── UI aufbauen ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = dict(padx=28, pady=0)

        # Header: Titel + Settings-Button
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=28, pady=(32, 2))

        tk.Label(header, text="HasisKocht",
                 font=self._f_title, bg=BG, fg=FG).pack(side="left")

        settings_lbl = tk.Label(header, text="⚙",
                                 font=tkfont.Font(size=18),
                                 bg=BG, fg=MUTED, cursor="hand2")
        settings_lbl.pack(side="right")
        settings_lbl.bind("<Button-1>", lambda _: self._show_key_dialog())

        tk.Label(self, text="YouTube-Video → Interaktives HTML-Rezept",
                 font=self._f_small, bg=BG, fg=MUTED).pack(anchor="w", **pad)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=28, pady=18)

        tk.Label(self, text="YouTube-URL",
                 font=self._f_label, bg=BG, fg=FG).pack(anchor="w", **pad)

        entry_frame = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER,
                               highlightthickness=1, bd=0)
        entry_frame.pack(fill="x", padx=28, pady=(6, 0))

        self._url_var = tk.StringVar()
        self._entry = tk.Entry(
            entry_frame, textvariable=self._url_var,
            font=self._f_label, bd=0, relief="flat",
            bg=CARD_BG, fg=FG, insertbackground=FG, highlightthickness=0,
        )
        self._entry.pack(fill="x", padx=10, pady=9)
        self._entry.bind("<Return>", lambda _: self._start_download())
        self._entry.bind("<FocusIn>",  lambda e: (
            entry_frame.config(highlightbackground=BLUE, highlightthickness=2),
            self._on_focus_in(e),
        ))
        self._entry.bind("<FocusOut>", lambda e: (
            entry_frame.config(highlightbackground=BORDER, highlightthickness=1),
            self._on_focus_out(e),
        ))

        self._placeholder = "https://www.youtube.com/watch?v=..."
        self._entry.insert(0, self._placeholder)
        self._entry.config(fg=MUTED)

        paste_btn = tk.Label(entry_frame, text="Einfügen", font=self._f_small,
                             bg=CARD_BG, fg=RED, cursor="hand2")
        paste_btn.place(relx=1.0, rely=0.5, anchor="e", x=-10)
        paste_btn.bind("<Button-1>", self._paste_url)

        self._btn_frame = tk.Frame(self, bg=BTN_BG, cursor="hand2")
        self._btn_frame.pack(fill="x", padx=28, pady=(16, 0))
        self._btn_lbl = tk.Label(
            self._btn_frame, text="Rezept erstellen",
            font=self._f_btn, bg=BTN_BG, fg=BTN_FG, cursor="hand2", pady=11,
        )
        self._btn_lbl.pack(fill="x")
        self._btn_enabled = True
        for widget in (self._btn_frame, self._btn_lbl):
            widget.bind("<Button-1>", lambda _: self._start_download() if self._btn_enabled else None)
            widget.bind("<Enter>", lambda _: self._set_btn_color(BTN_HOVER))
            widget.bind("<Leave>", lambda _: self._set_btn_color(BTN_BG))

        self._status_frame = tk.Frame(self, bg=BG)
        self._status_frame.pack(fill="x", padx=28, pady=(18, 0))

        self._status_icon = tk.Label(self._status_frame, text="",
                                     font=self._f_status, bg=BG)
        self._status_icon.pack(side="left")

        self._status_lbl = tk.Label(
            self._status_frame, text="", font=self._f_status,
            bg=BG, fg=FG, wraplength=440, justify="left",
        )
        self._status_lbl.pack(side="left", padx=(6, 0))

        folder_lbl = tk.Label(
            self, text="Dateien: Dokumente → Rezept-Transcripts",
            font=self._f_small, bg=BG, fg=MUTED, cursor="hand2",
        )
        folder_lbl.pack(anchor="w", padx=28, pady=(20, 0))
        folder_lbl.bind("<Button-1>", self._open_folder)

    # ── Hilfsmethoden ───────────────────────────────────────────────────────────
    def _set_btn_color(self, color):
        self._btn_frame.config(bg=color)
        self._btn_lbl.config(bg=color)

    def _set_btn_enabled(self, enabled: bool):
        self._btn_enabled = enabled
        self._set_btn_color("#e89090" if not enabled else BTN_BG)
        self._btn_lbl.config(fg=BTN_FG)

    def _on_focus_in(self, _event):
        if self._entry.get() == self._placeholder:
            self._entry.delete(0, "end")
            self._entry.config(fg=FG)

    def _on_focus_out(self, _event):
        if not self._entry.get():
            self._entry.insert(0, self._placeholder)
            self._entry.config(fg=MUTED)

    def _paste_url(self, _event=None):
        try:
            text = self.clipboard_get()
            self._entry.delete(0, "end")
            self._entry.config(fg=FG)
            self._entry.insert(0, text.strip())
        except tk.TclError:
            pass

    def _open_folder(self, _event=None):
        subprocess.Popen(["open", str(TRANSCRIPTS_DIR)])

    def _set_status(self, kind: str, message: str):
        icons  = {"ok": "✅", "error": "⚠️", "loading": "⏳", "generating": "🤖"}
        colors = {"ok": GREEN, "error": RED, "loading": FG, "generating": FG}
        self._status_icon.config(text=icons.get(kind, ""))
        self._status_lbl.config(text=message, fg=colors.get(kind, FG))

    # ── Download & Generierung ──────────────────────────────────────────────────
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
        # Phase 1: Transcript laden
        try:
            transcript_text, lang = fetch_transcript(video_id)
        except TranscriptsDisabled:
            self.after(0, self._set_status, "error",
                       "Für dieses Video sind Untertitel deaktiviert.")
            self.after(0, self._set_btn_enabled, True)
            return
        except NoTranscriptFound:
            self.after(0, self._set_status, "error",
                       "Kein Transcript für dieses Video gefunden.")
            self.after(0, self._set_btn_enabled, True)
            return
        except (RequestBlocked, IpBlocked):
            self.after(0, self._set_status, "error",
                       "YouTube blockiert die Anfrage. Bitte Internetverbindung prüfen.")
            self.after(0, self._set_btn_enabled, True)
            return
        except Exception as e:
            self.after(0, self._set_status, "error", f"Fehler: {e}")
            self.after(0, self._set_btn_enabled, True)
            return

        title = fetch_video_title(video_id)
        slug  = slugify(title)

        # Transcript als .txt speichern
        full_transcript = (
            f"YouTube Transcript: {title}\n"
            f"Video-ID: {video_id}\n"
            f"URL: https://www.youtube.com/watch?v={video_id}\n"
            f"Sprache: {lang}\n"
            + "=" * 60 + "\n\n"
            + transcript_text
        )
        txt_path = TRANSCRIPTS_DIR / f"{slug}_{lang}.txt"
        txt_path.write_text(full_transcript, encoding="utf-8")

        # Phase 2: Rezept via Groq generieren
        self.after(0, self._set_status, "generating", "Rezept wird generiert …")
        try:
            html_content = generate_recipe_html(full_transcript)
        except Exception as e:
            err = str(e)
            if any(k in err.lower() for k in ("auth", "api_key", "invalid_api", "unauthorized")):
                self.after(0, self._set_status, "error",
                           "Ungültiger API Key. Bitte über ⚙ einen gültigen Groq Key eingeben.")
            elif any(k in err.lower() for k in ("rate", "quota")):
                self.after(0, self._set_status, "error",
                           f"Groq Rate-Limit. Bitte 30 Sek. warten. ({err[:80]})")
            else:
                self.after(0, self._set_status, "error", f"Fehler: {err[:120]}")
            self.after(0, self._set_btn_enabled, True)
            return

        # HTML speichern
        html_path = TRANSCRIPTS_DIR / f"{slug}.html"
        html_path.write_text(html_content, encoding="utf-8")

        # Phase 3: Fertig
        self.after(0, self._set_status, "ok", "Fertig! Rezept öffnet sich im Browser.")
        self.after(0, self._set_btn_enabled, True)
        self.after(0, lambda: webbrowser.open(html_path.as_uri()))


if __name__ == "__main__":
    app = App()
    app.mainloop()
