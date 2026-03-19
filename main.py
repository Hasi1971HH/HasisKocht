"""
Entry point for the macOS app bundle.
Starts Flask in a background thread, then opens a native pywebview window.
"""
import os
import socket
import sys
import threading
import time

import webview


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def resource_path(relative: str) -> str:
    """Return absolute path – works both in development and inside .app bundle."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)


def start_flask(port: int) -> None:
    # Tell Flask where to find templates and static files when frozen
    from flask import Flask
    from youtube_transcript_api import (
        IpBlocked,
        NoTranscriptFound,
        RequestBlocked,
        TranscriptsDisabled,
        YouTubeTranscriptApi,
    )
    import re
    from flask import render_template, request, send_file, flash, redirect, url_for

    flask_app = Flask(
        __name__,
        template_folder=resource_path("templates"),
    )
    flask_app.secret_key = os.urandom(24)

    # Save transcripts to ~/Documents/Rezept-Transcripts so the user can find them
    transcripts_dir = os.path.join(
        os.path.expanduser("~"), "Documents", "Rezept-Transcripts"
    )
    os.makedirs(transcripts_dir, exist_ok=True)

    preferred_languages = ["de", "en", "fr", "es", "it"]

    def extract_video_id(url: str):
        patterns = [
            r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
            r"(?:embed/)([A-Za-z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def fetch_transcript(video_id: str):
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_manually_created_transcript(
                preferred_languages
            )
        except NoTranscriptFound:
            transcript = transcript_list.find_generated_transcript(preferred_languages)
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

    @flask_app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "POST":
            url = request.form.get("url", "").strip()
            if not url:
                flash("Bitte eine YouTube-URL eingeben.", "error")
                return redirect(url_for("index"))
            video_id = extract_video_id(url)
            if not video_id:
                flash("Ungültige YouTube-URL. Bitte überprüfe den Link.", "error")
                return redirect(url_for("index"))
            try:
                transcript_text, lang = fetch_transcript(video_id)
            except TranscriptsDisabled:
                flash("Für dieses Video sind Untertitel deaktiviert.", "error")
                return redirect(url_for("index"))
            except NoTranscriptFound:
                flash(
                    "Kein Transcript für dieses Video gefunden.",
                    "error",
                )
                return redirect(url_for("index"))
            except (RequestBlocked, IpBlocked):
                flash(
                    "YouTube blockiert die Anfrage. Bitte Internetverbindung prüfen.",
                    "error",
                )
                return redirect(url_for("index"))
            except Exception as e:
                flash(f"Fehler: {e}", "error")
                return redirect(url_for("index"))

            filename = f"transcript_{video_id}_{lang}.txt"
            filepath = os.path.join(transcripts_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("YouTube Transcript\n")
                f.write(f"Video-ID: {video_id}\n")
                f.write(f"URL: https://www.youtube.com/watch?v={video_id}\n")
                f.write(f"Sprache: {lang}\n")
                f.write("=" * 60 + "\n\n")
                f.write(transcript_text)

            return send_file(
                filepath,
                as_attachment=True,
                download_name=filename,
                mimetype="text/plain",
            )

        return render_template("index.html")

    flask_app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def wait_for_server(port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Flask server did not start in time.")


if __name__ == "__main__":
    port = find_free_port()

    server_thread = threading.Thread(target=start_flask, args=(port,), daemon=True)
    server_thread.start()

    wait_for_server(port)

    webview.create_window(
        title="Rezept Transcript Downloader",
        url=f"http://127.0.0.1:{port}",
        width=820,
        height=620,
        min_size=(600, 480),
    )
    webview.start()
