"""
py2app build script.

Usage (on macOS, in the project folder):

    pip install py2app pywebview
    python setup.py py2app

The resulting .app lands in dist/
"""
from setuptools import setup

APP = ["main.py"]

DATA_FILES = [
    ("templates", ["templates/index.html"]),
]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": None,          # replace with "icon.icns" once you have one
    "packages": [
        "flask",
        "webview",
        "youtube_transcript_api",
        "jinja2",
        "werkzeug",
        "click",
    ],
    "includes": [
        "importlib.metadata",
    ],
    "plist": {
        "CFBundleName": "Rezept Transcripts",
        "CFBundleDisplayName": "Rezept Transcripts",
        "CFBundleIdentifier": "de.hasiskocht.rezept-transcripts",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0",
        "NSHumanReadableCopyright": "Hasis Küche",
        "NSHighResolutionCapable": True,
    },
}

setup(
    name="Rezept Transcripts",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
