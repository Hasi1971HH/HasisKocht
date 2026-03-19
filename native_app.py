"""
Native macOS App — Rezept Transcript Downloader
Tkinter-basiert, kein Browser, kein Flask.
Lädt YouTube-Transcripts herunter und speichert sie in ~/Documents/Rezept-Transcripts.
"""
import os
import re
import threading
import tkinter as tk
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
TRANSCRIPTS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Rezept-Transcripts")
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)


# ── Farben & Stil ──────────────────────────────────────────────────────────────
BG         = "#f5f5f7"   # macOS-typisches Hellgrau
FG         = "#1d1d1f"
RED        = "#cc0000"
GREEN      = "#1a7f37"
CARD_BG    = "#ffffff"
BORDER     = "#d2d2d7"
BTN_BG     = "#cc0000"
BTN_FG     = "#ffffff"
BTN_HOVER  = "#a30000"
MUTED      = "#6e6e73"


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


# ── Haupt-App ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Rezept Transcripts")
        self.resizable(False, False)
        self.configure(bg=BG)

        # Fenster zentrieren
        w, h = 520, 400
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        # Schriften
        self._f_title  = tkfont.Font(family="SF Pro Display", size=20, weight="bold")
        self._f_label  = tkfont.Font(family="SF Pro Text",    size=13)
        self._f_small  = tkfont.Font(family="SF Pro Text",    size=11)
        self._f_btn    = tkfont.Font(family="SF Pro Text",    size=13, weight="bold")
        self._f_status = tkfont.Font(family="SF Pro Text",    size=12)

        self._build_ui()

    # ── UI aufbauen ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = dict(padx=28, pady=0)

        # Titel
        tk.Label(
            self, text="Rezept Transcripts",
            font=self._f_title, bg=BG, fg=FG,
        ).pack(anchor="w", padx=28, pady=(32, 2))

        tk.Label(
            self, text="YouTube-Transcript als Textdatei herunterladen",
            font=self._f_small, bg=BG, fg=MUTED,
        ).pack(anchor="w", **pad)

        # Trennlinie
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=28, pady=18)

        # URL-Label + Feld
        tk.Label(
            self, text="YouTube-URL", font=self._f_label, bg=BG, fg=FG,
        ).pack(anchor="w", **pad)

        entry_frame = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER,
                               highlightthickness=1, bd=0)
        entry_frame.pack(fill="x", padx=28, pady=(6, 0))

        self._url_var = tk.StringVar()
        self._entry = tk.Entry(
            entry_frame,
            textvariable=self._url_var,
            font=self._f_label,
            bd=0, relief="flat",
            bg=CARD_BG, fg=FG,
            insertbackground=FG,
        )
        self._entry.pack(fill="x", padx=10, pady=9)
        self._entry.bind("<Return>", lambda _: self._start_download())

        # Platzhaltertext
        self._placeholder = "https://www.youtube.com/watch?v=..."
        self._entry.insert(0, self._placeholder)
        self._entry.config(fg=MUTED)
        self._entry.bind("<FocusIn>",  self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)

        # Einfügen-Button (klein, neben dem Feld)
        paste_btn = tk.Label(
            entry_frame, text="Einfügen", font=self._f_small,
            bg=CARD_BG, fg=RED, cursor="hand2",
        )
        paste_btn.place(relx=1.0, rely=0.5, anchor="e", x=-10)
        paste_btn.bind("<Button-1>", self._paste_url)

        # Download-Button
        self._btn = tk.Button(
            self, text="Transcript herunterladen",
            font=self._f_btn,
            bg=BTN_BG, fg=BTN_FG,
            activebackground=BTN_HOVER, activeforeground=BTN_FG,
            relief="flat", bd=0,
            cursor="hand2",
            command=self._start_download,
        )
        self._btn.pack(fill="x", padx=28, pady=(16, 0), ipady=11)
        self._btn.bind("<Enter>", lambda _: self._btn.config(bg=BTN_HOVER))
        self._btn.bind("<Leave>", lambda _: self._btn.config(bg=BTN_BG))

        # Spinner / Status-Bereich
        self._status_frame = tk.Frame(self, bg=BG)
        self._status_frame.pack(fill="x", padx=28, pady=(18, 0))

        self._status_icon = tk.Label(self._status_frame, text="", font=self._f_status,
                                     bg=BG)
        self._status_icon.pack(side="left")

        self._status_lbl = tk.Label(
            self._status_frame, text="", font=self._f_status, bg=BG, fg=FG,
            wraplength=440, justify="left",
        )
        self._status_lbl.pack(side="left", padx=(6, 0))

        # Ordner-Hinweis
        folder_lbl = tk.Label(
            self,
            text=f"Dateien: Dokumente → Rezept-Transcripts",
            font=self._f_small, bg=BG, fg=MUTED, cursor="hand2",
        )
        folder_lbl.pack(anchor="w", padx=28, pady=(20, 0))
        folder_lbl.bind("<Button-1>", self._open_folder)

    # ── Platzhalter ─────────────────────────────────────────────────────────────
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
        import subprocess
        subprocess.Popen(["open", TRANSCRIPTS_DIR])

    # ── Download ────────────────────────────────────────────────────────────────
    def _start_download(self):
        url = self._url_var.get().strip()
        if not url or url == self._placeholder:
            self._set_status("error", "Bitte eine YouTube-URL eingeben.")
            return

        video_id = extract_video_id(url)
        if not video_id:
            self._set_status("error", "Ungültige YouTube-URL. Bitte überprüfe den Link.")
            return

        self._btn.config(state="disabled")
        self._set_status("loading", "Transcript wird geladen …")
        threading.Thread(target=self._download, args=(video_id,), daemon=True).start()

    def _download(self, video_id: str):
        try:
            transcript_text, lang = fetch_transcript(video_id)
        except TranscriptsDisabled:
            self.after(0, self._set_status, "error",
                       "Für dieses Video sind Untertitel deaktiviert.")
            self.after(0, self._btn.config, {"state": "normal"})
            return
        except NoTranscriptFound:
            self.after(0, self._set_status, "error",
                       "Kein Transcript für dieses Video gefunden.")
            self.after(0, self._btn.config, {"state": "normal"})
            return
        except (RequestBlocked, IpBlocked):
            self.after(0, self._set_status, "error",
                       "YouTube blockiert die Anfrage. Bitte Internetverbindung prüfen.")
            self.after(0, self._btn.config, {"state": "normal"})
            return
        except Exception as e:
            self.after(0, self._set_status, "error", f"Fehler: {e}")
            self.after(0, self._btn.config, {"state": "normal"})
            return

        filename = f"transcript_{video_id}_{lang}.txt"
        filepath = os.path.join(TRANSCRIPTS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("YouTube Transcript\n")
            f.write(f"Video-ID: {video_id}\n")
            f.write(f"URL: https://www.youtube.com/watch?v={video_id}\n")
            f.write(f"Sprache: {lang}\n")
            f.write("=" * 60 + "\n\n")
            f.write(transcript_text)

        self.after(0, self._set_status, "ok",
                   f"Gespeichert: {filename}")
        self.after(0, self._btn.config, {"state": "normal"})
        # Ordner automatisch im Finder öffnen
        import subprocess
        self.after(0, lambda: subprocess.Popen(["open", "-R", filepath]))

    # ── Status-Anzeige ──────────────────────────────────────────────────────────
    def _set_status(self, kind: str, message: str):
        icons  = {"ok": "✅", "error": "⚠️", "loading": "⏳"}
        colors = {"ok": GREEN, "error": RED, "loading": FG}
        self._status_icon.config(text=icons.get(kind, ""))
        self._status_lbl.config(text=message, fg=colors.get(kind, FG))


if __name__ == "__main__":
    app = App()
    app.mainloop()
