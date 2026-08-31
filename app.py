import logging
import os
import shutil
import subprocess
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

import database
import parser
import paths
import voice_params

log = logging.getLogger("dx7.app")

# No CORS middleware: the SPA is served from this same origin and every fetch()
# in static/app.js uses a root-relative /api/... path, so it is never exercised.
# It also can't be configured correctly now that the desktop launcher binds an
# ephemeral port. If it is ever needed again, use
# allow_origin_regex=r"^http://(127\.0\.0\.1|localhost)(:\d+)?$" -- never a
# hardcoded list of origins.

# Serializes the destructive operations against each other. Endpoints are
# declared `def`, so Starlette runs them in a threadpool and two requests really
# can interleave: without this, two concurrent scans each call clear_db() and
# wipe the other's inserts, and whichever finishes first reports "idle" while
# the other is still writing.
_scan_lock = threading.Lock()

# Global scan state
scan_state = {
    "status": "idle",
    "files_scanned": 0,
    "total_files": 0,
    "current_file": "",
    "voices_found": 0,
    "error": None
}

# Marker file recording that the bundled demo patches have been installed once.
# Deliberately a file rather than an "is the voices table empty?" check, so that
# using Clear Database does not silently resurrect the demo data.
DEMO_SENTINEL = "demo_seeded.marker"


def _seed_demo_data():
    """First run only: install the bundled sample patches and index them.

    The patches are copied out of the resource dir before being scanned. Under
    a onefile build the resource dir is an ephemeral %TEMP%\\_MEIxxxxxx path
    that is deleted on exit, so scanning them in place would write absolute
    paths into the database that are dead on the next launch -- breaking both
    Reveal in Explorer and the Voice Parameters page.

    Never fatal: the app is fully usable without demo data.
    """
    marker = paths.user_data_dir() / DEMO_SENTINEL
    if marker.exists():
        return

    try:
        # run_background_scan() calls database.clear_db() before indexing, so
        # seeding a database that already holds voices would destroy the user's
        # index. That happens on the upgrade path: an existing install has a
        # populated database but no sentinel yet. Claim the sentinel and leave
        # their data alone.
        if database.count_voices() > 0:
            marker.write_text("1", encoding="utf-8")
            log.info("Existing voice index found; skipping demo data seeding.")
            return

        src = paths.resource_path("sample_patches")
        if src.is_dir():
            dst = paths.demo_patches_dir()
            shutil.copytree(src, dst, dirs_exist_ok=True)
            # 3 files / ~24 KB, so this runs in well under 50 ms. Lifespan is
            # awaited before the server accepts connections, so the very first
            # request already sees a populated database -- no loading flicker.
            run_background_scan(str(dst))
        marker.write_text("1", encoding="utf-8")
    except Exception:
        log.exception("Demo data seeding failed; continuing without it.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    _seed_demo_data()
    yield


app = FastAPI(title="Yamaha DX7 Voice Browser", lifespan=lifespan)

# Hosts this server is willing to answer to. Anything else means the request
# arrived under a name that resolves here without being "localhost" -- i.e. DNS
# rebinding, which is the one way a remote page gets same-origin access to a
# loopback server.
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}


@app.middleware("http")
async def _guard_local_origin(request: Request, call_next):
    """Rejects requests that did not come from this app's own page.

    The server binds 127.0.0.1 on an ephemeral port with no authentication. A
    browser's same-origin policy is what normally keeps other pages out, but it
    is defeated by DNS rebinding: a page on evil.example whose DNS re-resolves
    to 127.0.0.1 becomes same-origin with us, and can then POST to the scan,
    clear and delete endpoints with no preflight.

    Two cheap checks close that. The Host header must name loopback (a rebound
    request carries the attacker's domain), and any Origin/Referer present must
    also be loopback.
    """
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
    if host and host not in {h.strip("[]") for h in _ALLOWED_HOSTS}:
        log.warning("Rejected request with non-local Host header: %r", host)
        return JSONResponse({"detail": "Invalid Host header."}, status_code=403)

    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin:
        from urllib.parse import urlparse
        origin_host = (urlparse(origin).hostname or "")
        if origin_host and origin_host not in _ALLOWED_HOSTS:
            log.warning("Rejected cross-origin request from %r", origin)
            return JSONResponse({"detail": "Cross-origin requests are not allowed."},
                                status_code=403)

    return await call_next(request)


class ScanRequest(BaseModel):
    directory: str

class RevealRequest(BaseModel):
    file_path: str

class DeleteFolderRequest(BaseModel):
    folder_path: str

def run_background_scan(directory_path: str):
    global scan_state
    try:
        # 1. Gather all .syx files recursively
        syx_files = []
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.lower().endswith('.syx'):
                    abs_path = os.path.abspath(os.path.join(root, file))
                    syx_files.append(abs_path)
        
        total = len(syx_files)
        scan_state["total_files"] = total
        scan_state["files_scanned"] = 0
        scan_state["voices_found"] = 0
        scan_state["error"] = None
        
        if total == 0:
            # Report this rather than silently keeping the previous index while
            # the UI says "Cataloged 0 patches".
            scan_state["error"] = f"No .syx files found in {directory_path}"
            log.info("Scan found no .syx files in %s", directory_path)
            scan_state["status"] = "idle"
            return
        
        # 2. Clear database to start fresh
        database.clear_db()
        
        # 3. Parse files and insert records.
        # One connection for the whole scan, committed in batches -- see
        # database.BulkVoiceWriter.
        with database.BulkVoiceWriter() as writer:
            for file_path in syx_files:
                scan_state["current_file"] = os.path.basename(file_path)
            
                # Extract voices from .syx
                parsed_voices = parser.parse_syx_file(file_path)
            
                if parsed_voices:
                    db_voices = []
                    # Normalize to forward slashes for consistent cross-platform DB storage
                    folder_path = os.path.dirname(file_path).replace('\\', '/')
                    file_path_norm = file_path.replace('\\', '/')
                    file_name = os.path.basename(file_path)

                    for pv in parsed_voices:
                        db_voices.append({
                            "voice_name": pv["name"],
                            "folder_path": folder_path,
                            "file_name": file_name,
                            "file_path": file_path_norm,
                            "position": pv["position"],
                            "patch_type": pv.get("patch_type", "Voice"),
                        })
                
                    writer.add(db_voices)
                    scan_state["voices_found"] += len(db_voices)
            
                scan_state["files_scanned"] += 1
            
    except Exception as e:
        log.exception("Scan of %s failed", directory_path)
        scan_state["error"] = str(e)
    finally:
        scan_state["status"] = "idle"
        scan_state["current_file"] = ""

@app.post("/api/scan")
def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    global scan_state
    
    dir_path = request.directory.strip()
    if not dir_path or not os.path.isdir(dir_path):
        raise HTTPException(status_code=400, detail="Invalid directory path.")
    
    # Check-and-set under one lock. Without it two concurrent requests can both
    # pass the status check before either sets it, and two scans then interleave
    # -- the second's clear_db() wiping the first's inserts.
    with _scan_lock:
        if scan_state["status"] == "scanning":
            raise HTTPException(status_code=400, detail="A scan is already in progress.")

        scan_state["status"] = "scanning"
        scan_state["files_scanned"] = 0
        scan_state["total_files"] = 0
        scan_state["voices_found"] = 0
        scan_state["current_file"] = ""
        scan_state["error"] = None
    
    # Run the scanning process in a background thread to keep API responsive
    background_tasks.add_task(run_background_scan, dir_path)
    
    return {"message": "Scan started."}

@app.get("/api/scan-status")
def get_scan_status():
    return scan_state

@app.post("/api/browse-folder")
def browse_folder():
    """Opens a native OS folder picker dialog and returns the selected path.

    POST, not GET: a GET with no custom headers is a CORS "simple request", so
    any page could fire it with an <img> tag and pop a native folder dialog over
    the user's desktop -- and each pending dialog holds a threadpool worker.

    Two backends. In the packaged desktop app the dialog goes through pywebview,
    which marshals it onto the WinForms GUI thread and blocks the caller -- safe
    to call from Starlette's threadpool, and the dialog is properly parented to
    the app window. tkinter remains the fallback for the bare `uvicorn app:app`
    dev flow, where no window exists; it is excluded from the frozen build.

    Returns {"path": <str|None>} either way -- None means the user cancelled.
    """
    try:
        import webview
    except ImportError:
        webview = None

    if webview is not None and getattr(webview, "windows", None):
        try:
            # FileDialog.FOLDER in pywebview 6.x; FOLDER_DIALOG is the
            # deprecated alias kept for older versions.
            folder_type = getattr(
                getattr(webview, "FileDialog", None), "FOLDER", None
            )
            if folder_type is None:
                folder_type = webview.FOLDER_DIALOG
            result = webview.windows[0].create_file_dialog(folder_type)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not open folder dialog: {e}")
        if not result:
            return {"path": None}
        # Returns a sequence of paths; older versions returned a bare string.
        return {"path": result if isinstance(result, str) else result[0]}

    # --- dev fallback: no pywebview window, use tkinter ---
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', True)
        folder = filedialog.askdirectory(title="Select folder to scan", parent=root)
        root.destroy()
        return {"path": folder or None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not open folder dialog: {e}")


@app.get("/api/app-info")
def app_info():
    """Where the app keeps its files. Used by the front-end to prefill the scan
    field with the bundled demo patches on first run."""
    return {
        "demo_path": str(paths.demo_patches_dir()),
        "data_dir": str(paths.user_data_dir()),
        "frozen": paths.is_frozen(),
    }

@app.get("/api/folders")
def get_folders():
    """Returns all unique folder paths currently indexed in the database."""
    try:
        return database.get_all_folders()
    except Exception as e:
        log.exception("get_folders failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/voices")
def get_voices(q: Optional[str] = None,
               folder: Optional[str] = None,
               patch_type: Optional[str] = None):
    try:
        return database.get_all_voices(q, folder, patch_type)
    except Exception as e:
        log.exception("get_voices failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/voices/files")
def get_voices_files(name: str, patch_type: Optional[str] = None):
    """
    Returns every individual record matching name (and optionally patch_type).
    Used by the frontend to populate the duplicate-files detail modal.
    """
    try:
        files = database.get_voices_by_name(name, patch_type)
        return files
    except Exception as e:
        log.exception("get_voices_files failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/voices/{voice_id}/parameters")
def get_voice_parameters(voice_id: int):
    """
    Returns the fully decoded synthesis parameters (operators, envelopes, LFO,
    pitch EG, and — for Gen 2 Extended voices — key mode/pitch bend/portamento/
    controllers) for a single voice, re-read from its source .syx file.
    """
    row = database.get_voice_by_id(voice_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Voice not found.")

    if row["patch_type"] == "Performance":
        raise HTTPException(
            status_code=400,
            detail="Performances aren't single voices — parameters aren't applicable."
        )

    try:
        occurrence_index = database.get_voice_occurrence_index(voice_id, row["file_path"])
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail="Could not locate this voice's data — the source file may have "
                    "changed since the last scan. Try re-scanning its folder."
        )

    blocks = parser.extract_voice_blocks(row["file_path"])
    if occurrence_index >= len(blocks):
        raise HTTPException(
            status_code=409,
            detail="Could not re-read this voice from its source file — it may have "
                    "been moved, deleted, or modified since the last scan. Try "
                    "re-scanning its folder."
        )

    block = blocks[occurrence_index]
    core_bytes = block.get("_core_bytes")
    if core_bytes is None:
        raise HTTPException(
            status_code=409,
            detail="This voice's core parameter data is missing from its source "
                    "file. Try re-scanning its folder."
        )

    params = voice_params.build_voice_parameters(core_bytes, block.get("_additional_bytes"))

    return {
        "id": row["id"],
        "voice_name": row["voice_name"],
        "patch_type": row["patch_type"],
        "folder_path": row["folder_path"],
        "file_name": row["file_name"],
        "file_path": row["file_path"],
        "position": row["position"],
        **params,
    }

@app.get("/api/duplicates")
def get_duplicates():
    """
    Analyzes the database and returns groups of folders with identical .syx content.
    Only groups with >= 2 folders are returned.
    """
    try:
        return database.get_duplicate_folder_groups()
    except Exception as e:
        log.exception("get_duplicates failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/delete-folder")
def delete_folder_endpoint(request: DeleteFolderRequest):
    """
    Deletes the entire directory tree for folder_path from disk and removes
    all matching records from the database.
    Body: { "folder_path": "C:\\..." }
    """
    folder_path = request.folder_path.strip()
    if not folder_path:
        raise HTTPException(status_code=400, detail="folder_path is required.")
    # Deleting while a scan rewrites the index leaves the two inconsistent.
    if scan_state["status"] == "scanning":
        raise HTTPException(status_code=409, detail="A scan is in progress.")
    try:
        result = database.delete_folder(folder_path)
        status_code = 500 if result['error'] else 200
        return JSONResponse(content=result, status_code=status_code)
    except Exception as e:
        # Return the same {error: ...} shape as the expected failure path, so
        # the client cannot mistake a crash here for a successful delete.
        log.exception("delete-folder failed for %s", folder_path)
        return JSONResponse(
            content={'deleted_path': folder_path,
                     'had_indexed_subfolders': False,
                     'error': str(e)},
            status_code=500,
        )

@app.post("/api/clear")
def clear_voices():
    # A scan writes continuously; clearing underneath it leaves a partial index.
    if scan_state["status"] == "scanning":
        raise HTTPException(status_code=409, detail="A scan is in progress.")
    try:
        database.clear_db()
        return {"message": "Database cleared successfully."}
    except Exception as e:
        log.exception("Failed to clear database")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reveal")
def reveal_in_explorer(request: RevealRequest):
    file_path = request.file_path
    # Only reveal files we actually indexed. Without this the endpoint is a
    # filesystem-existence oracle for any local page, and can be used to spawn
    # unlimited Explorer windows.
    if not database.is_indexed_file(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    
    try:
        # On Windows, using explorer /select, <path> opens explorer and highlights the file.
        #
        # The DEVNULL handles are required under a --windowed PyInstaller build:
        # there sys.stdin/stdout/stderr are None and the underlying OS handles
        # are invalid, so the default "inherit the parent's handles" behaviour
        # can raise OSError: [WinError 6] The handle is invalid.
        # check=False because explorer.exe returns exit code 1 even on success.
        # Absolute path: a bare "explorer" is resolved through a search path
        # that includes the current working directory, so launching the app from
        # an attacker-writable folder could run a planted explorer.exe.
        explorer = os.path.join(
            os.environ.get("WINDIR", r"C:\Windows"), "explorer.exe"
        )
        subprocess.run(
            [explorer, '/select,', os.path.normpath(file_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            check=False,
        )
        return {"message": "Folder opened successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open explorer: {e}")

# Mount static files to serve the front-end SPA
# Note: Place this after the API routes so it doesn't shadow them
_static_dir = paths.resource_path("static")
if not _static_dir.is_dir():
    # Fail loudly. This used to be os.makedirs("static", exist_ok=True), which
    # created an empty directory relative to the working directory and then
    # served 404s for the whole SPA -- and under a frozen build would have
    # littered a stray static\ folder wherever the user double-clicked.
    raise RuntimeError(f"Bundled static assets are missing: {_static_dir}")

app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
