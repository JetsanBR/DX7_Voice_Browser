"""Single source of truth for every filesystem path the app touches.

The current working directory is never consulted. Three execution modes must
all resolve correctly:

  (a) ``python main.py`` from the repo  -> __file__ lives in the repo root
  (b) ``uvicorn app:app`` (dev flow)    -> same, and CWD-independent
  (c) PyInstaller onefile               -> sys._MEIPASS is the temp extract dir

Two kinds of location, and the distinction matters:

  * **Resources** are read-only files shipped with the app (``static/``,
    ``sample_patches/``). Under a onefile build they live in an ephemeral
    ``%TEMP%\\_MEIxxxxxx`` directory that is deleted when the process exits, so
    nothing that must survive a restart may be stored there -- and no absolute
    path pointing into it may be written to the database.
  * **User data** is everything writable (the voice index, logs, the WebView2
    profile). It lives under ``%LOCALAPPDATA%`` so it persists across launches
    and works even when the app is installed somewhere unwritable.
"""

import os
import sys
from pathlib import Path

APP_NAME = "DX7VoiceBrowser"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def resource_root() -> Path:
    """Directory holding the read-only bundled assets.

    Frozen onefile : %TEMP%\\_MEIxxxxxx  (recreated each launch, then deleted)
    Frozen onedir  : <exe dir>\\_internal
    From source    : the directory holding this file -- NOT the CWD.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    """Path to a bundled resource, e.g. ``resource_path("static")``."""
    return resource_root().joinpath(*parts)


def user_data_dir() -> Path:
    """Writable per-user state directory, created on first access.

    Set DX7_DATA_DIR to override (used by tests, and by anyone who wants a
    portable install that keeps its data next to the executable).
    """
    override = os.environ.get("DX7_DATA_DIR")
    if override:
        base = Path(override).expanduser()
    else:
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(local) if local else Path.home() / "AppData" / "Local"
        base = root / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    """The SQLite voice index."""
    return user_data_dir() / "voices.db"


def log_path() -> Path:
    """Log file. Under a --windowed build this is the only diagnostic output."""
    return user_data_dir() / "dx7browser.log"


def demo_patches_dir() -> Path:
    """Where the bundled sample patches are copied to on first run.

    They cannot be scanned in place: under a onefile build they live in the
    ephemeral resource dir, so the absolute paths written into the database
    would be dead on the next launch.
    """
    return user_data_dir() / "sample_patches"


def webview_storage_dir() -> Path:
    """WebView2 profile (cookies, local storage, cache)."""
    return user_data_dir() / "webview"
