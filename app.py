import os
import re
import requests
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
    RequestBlocked,
    IpBlocked,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

TRANSCRIPTS_DIR = "transcripts"
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

PREFERRED_LANGUAGES = ["de", "en", "fr", "es", "it"]


def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_video_title(video_id: str) -> str:
    """Fetch video title from YouTube page title tag."""
    try:
        resp = requests.get(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={"Accept-Language": "de,en;q=0.9"},
            timeout=10,
        )
        match = re.search(r"<title>(.+?)\s*-\s*YouTube</title>", resp.text)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return video_id


def fetch_transcript(video_id: str) -> tuple[str, str]:
    """Returns (transcript_text, language_code)."""
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)

    # Prefer manual transcripts, then auto-generated
    try:
        transcript = transcript_list.find_manually_created_transcript(
            PREFERRED_LANGUAGES
        )
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


@app.route("/", methods=["GET", "POST"])
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
                "Kein Transcript für dieses Video gefunden. "
                "Versuche es mit einer anderen Spracheinstellung.",
                "error",
            )
            return redirect(url_for("index"))
        except (RequestBlocked, IpBlocked):
            flash(
                "YouTube blockiert die Anfrage von diesem Server. "
                "Bitte die App lokal ausführen.",
                "error",
            )
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Fehler beim Laden des Transcripts: {e}", "error")
            return redirect(url_for("index"))

        title = fetch_video_title(video_id)
        safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)[:80]
        filename = f"{safe_title}_{lang}.txt"
        filepath = os.path.join(TRANSCRIPTS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"YouTube Transcript\n")
            f.write(f"Titel: {title}\n")
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


if __name__ == "__main__":
    app.run(debug=True)
