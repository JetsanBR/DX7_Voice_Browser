<#
.SYNOPSIS
    Starts the DX7 Voice Browser in the browser-based dev flow.

.DESCRIPTION
    Serves the app at http://127.0.0.1:8000 with auto-reload, for front-end work
    where reload and browser devtools are worth more than the real window.

    This is NOT what end users run. For the desktop app -- the native window,
    the pywebview folder picker, an ephemeral port -- run `python main.py`, or
    build the executable with `pyinstaller dx7_voice_browser.spec`.

    Prefers .buildvenv (which also has pywebview and PyInstaller) and falls back
    to venv. Both flows read and write the same database in
    %LOCALAPPDATA%\DX7VoiceBrowser; set DX7_DATA_DIR to point somewhere else.
#>

$ErrorActionPreference = 'Stop'

$venv = if (Test-Path "$PSScriptRoot\.buildvenv\Scripts\Activate.ps1") {
    "$PSScriptRoot\.buildvenv"
} else {
    "$PSScriptRoot\venv"
}

if (-not (Test-Path "$venv\Scripts\Activate.ps1")) {
    throw "No virtual environment found. See the Setup section of README.md."
}

& "$venv\Scripts\Activate.ps1"

# --app-dir keeps `app:app` importable no matter where this is invoked from.
# (Resource and database paths are CWD-independent regardless -- see paths.py.)
uvicorn app:app --reload --host 127.0.0.1 --port 8000 --app-dir $PSScriptRoot
