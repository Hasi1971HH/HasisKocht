"""
py2app build script for the NATIVE Tkinter app (no Flask, no webview).

Usage (on macOS, in the project folder):

    pip install py2app
    python setup_native.py py2app

The resulting .app lands in dist/
"""
from setuptools import setup

APP = ["native_app.py"]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": None,   # replace with "icon.icns" once you have one
    "packages": [
        "youtube_transcript_api",
        "groq",
        "httpx",
        "httpcore",
        "anyio",
        "distro",
        "sniffio",
    ],
    "includes": [
        "tkinter",
        "importlib.metadata",
        "json",
        "webbrowser",
    ],
    "plist": {
        "CFBundleName": "HasisKocht",
        "CFBundleDisplayName": "HasisKocht",
        "CFBundleIdentifier": "de.hasiskocht.native",
        "CFBundleVersion": "2.0.0",
        "CFBundleShortVersionString": "2.0",
        "NSHumanReadableCopyright": "Hasis Küche",
        "NSHighResolutionCapable": True,
    },
}

setup(
    name="HasisKocht",
    app=APP,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
