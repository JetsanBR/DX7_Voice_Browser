import os
import subprocess
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

import database
import parser

app = FastAPI(title="Yamaha DX7 Voice Browser")

# Enable CORS for development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Global scan state
scan_state = {
    "status": "idle",
    "files_scanned": 0,
    "total_files": 0,
    "current_file": "",
    "voices_found": 0,
    "error": None
}

# Ensure database is initialized on startup
@app.on_event("startup")
def startup_event():
    database.init_db()

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
            scan_state["status"] = "idle"
            return
        
        # 2. Clear database to start fresh
        database.clear_db()
        
        # 3. Parse files and insert records
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
                
                database.insert_voices(db_voices)
                scan_state["voices_found"] += len(db_voices)
            
            scan_state["files_scanned"] += 1
            
    except Exception as e:
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

@app.get("/api/folders")
def get_folders():
    """Returns all unique folder paths currently indexed in the database."""
    try:
        return database.get_all_folders()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/voices")
def get_voices(q: Optional[str] = None,
               folder: Optional[str] = None,
               patch_type: Optional[str] = None):
    try:
        return database.get_all_voices(q, folder, patch_type)
    except Exception as e:
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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/duplicates")
def get_duplicates():
    """
    Analyzes the database and returns groups of folders with identical .syx content.
    Only groups with >= 2 folders are returned.
    """
    try:
        return database.get_duplicate_folder_groups()
    except Exception as e:
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
    try:
        result = database.delete_folder(folder_path)
        status_code = 500 if result['error'] else 200
        return JSONResponse(content=result, status_code=status_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clear")
def clear_voices():
    try:
        database.clear_db()
        return {"message": "Database cleared successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reveal")
def reveal_in_explorer(request: RevealRequest):
    file_path = request.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    
    try:
        # On Windows, using explorer /select, <path> opens explorer and highlights the file
        subprocess.run(['explorer', '/select,', os.path.normpath(file_path)])
        return {"message": "Folder opened successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open explorer: {e}")

# Mount static files to serve the front-end SPA
# Note: Place this after the API routes so it doesn't shadow them
os.makedirs("static", exist_ok=True)

app.mount("/", StaticFiles(directory="static", html=True), name="static")
