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

# NOTE: webview/lib (the WebView2 interop assemblies) and webview/js are NOT
# listed here. pywebview ships its own PyInstaller hook via the `pyinstaller40`
# entry point, and pyinstaller-hooks-contrib carries an identical one; both are
# auto-discovered regardless of hookspath, and adding them by hand here only
# duplicated what the hooks already collect.

# ---------------------------------------------------------------------------
# Hidden imports: everything resolved by *string* at runtime rather than by an
# import statement, so the module graph never sees it.
# ---------------------------------------------------------------------------
# Only the ones the toolchain cannot work out for itself. uvicorn's submodules
# and anyio's backends are already covered by pyinstaller-hooks-contrib
# (hook-uvicorn.py does collect_submodules('uvicorn'), hook-anyio.py does
# collect_submodules('anyio._backends')), so listing them here was redundant.
hiddenimports = [
    # pywebview picks its platform module by string at runtime -- main.py passes
    # gui="edgechromium" -- so the module graph cannot see these.
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    # Naming clr explicitly is what makes hooks-contrib's hook-clr.py fire, and
    # that hook is what locates Python.Runtime.dll. Without it pythonnet dies at
    # startup and the window never appears.
    "clr",
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
    #
    # setuptools itself IS excluded: nothing in the app imports it, and
    # _distutils_hack drags in ~130 modules (over 10% of the bundled Python
    # source). Exclude the three together -- excluding setuptools while
    # _distutils_hack is still live is exactly the failure noted above.
    "setuptools", "_distutils_hack", "pkg_resources",
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
    # optimize=0 is the default, kept explicit because it matters here: -O
    # strips `assert` statements, and h11/anyio/starlette use asserts as
    # internal state-machine invariants, which turns loud failures into silent
    # corruption. (-OO would additionally strip the docstrings FastAPI reads for
    # OpenAPI.) Annotations are unaffected by either, so pydantic is not the
    # reason.
    optimize=0,
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
