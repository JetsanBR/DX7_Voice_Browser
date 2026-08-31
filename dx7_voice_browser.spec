# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the DX7 Voice Browser desktop app.

    pyinstaller --noconfirm --clean dx7_voice_browser.spec      -> dist/DX7VoiceBrowser.exe

Set DX7_BUILD_CONSOLE=1 to build a console variant instead. Do that first when
something is wrong: the windowed build has no stdout, so a failure there looks
like "nothing happens when I double-click".
"""

import os
from pathlib import Path

ROOT = Path(SPECPATH)  # noqa: F821 - injected by PyInstaller
APP_NAME = "DX7VoiceBrowser"
CONSOLE = bool(os.environ.get("DX7_BUILD_CONSOLE"))

# ---------------------------------------------------------------------------
# Data files.
#
# Listed one by one on purpose. Never glob the repo root: it holds the author's
# own voices.db (~97 MB of scanned data, including absolute paths from their
# filesystem), the venvs, and the design handoff folders. A wildcard here would
# ship all of it.
# ---------------------------------------------------------------------------
datas = [
    (str(ROOT / "static"), "static"),                  # SPA + vendored fonts/icons
    (str(ROOT / "sample_patches"), "sample_patches"),  # demo data, copied out on first run
]

# pywebview loads its native/managed interop assemblies out of webview/lib by
# filename at runtime. They are not importable modules, so PyInstaller's module
# graph cannot discover them.
import webview  # noqa: E402

_webview_lib = Path(webview.__file__).parent / "lib"
if _webview_lib.is_dir():
    datas.append((str(_webview_lib), "webview/lib"))

# ---------------------------------------------------------------------------
# Hidden imports: everything resolved by *string* at runtime rather than by an
# import statement, so the module graph never sees it.
# ---------------------------------------------------------------------------
hiddenimports = [
    # uvicorn resolves these through importlib in uvicorn/importer.py, using the
    # names in its config tables. main.py pins loop/http/ws/lifespan explicitly,
    # but the "auto" shims are included so a bare `uvicorn app:app` would also
    # work inside the bundle.
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "uvicorn.logging",
    # anyio picks its backend by string; Starlette's threadpool needs it, which
    # is what every sync endpoint in app.py runs on.
    "anyio._backends._asyncio",
    # pywebview picks its platform module by string.
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    # pythonnet, the bridge WinForms is reached through.
    "clr",
    "clr_loader",
]

# ---------------------------------------------------------------------------
# Excludes. tkinter is the big one: Tcl/Tk adds ~10-15 MB to a "single file"
# executable, and the packaged app never reaches the tkinter branch of
# /api/browse-folder because pywebview always provides the dialog.
# ---------------------------------------------------------------------------
excludes = [
    "tkinter", "_tkinter", "turtle", "turtledemo",
    "test", "unittest", "doctest", "pydoc", "pydoc_data", "lib2to3",
    # NB: do not exclude "distutils". Since Python 3.12 it is no longer stdlib
    # and is injected by setuptools' _distutils_hack, so excluding it makes
    # PyInstaller fail with "already imported as ExcludedModule".
    "pip",
    "numpy", "PIL", "matplotlib", "pandas", "scipy",
    "uvloop", "httptools", "watchfiles", "websockets", "wsproto",
    "yaml", "dotenv",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "gi", "cefpython3",
]

a = Analysis(  # noqa: F821
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,  # keep docstrings: pydantic reads annotations at import time
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX stays OFF. It is the single biggest driver of Defender/SmartScreen
    # false positives on PyInstaller onefile builds, and has a history of
    # corrupting pythonnet and WebView2 native DLLs.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,  # onefile: extract to %TEMP%\_MEIxxxxxx
    console=CONSOLE,
    # Keep the traceback dialog. Without it a crash in the windowed build is
    # completely silent, and the only bug report you get is "it just closes".
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "dx7.ico"),
    version=str(ROOT / "assets" / "version_info.txt"),
)
