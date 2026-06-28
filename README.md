# Yamaha DX7 Voice Browser

A local web application for cataloging, searching, and locating Yamaha DX7 / DX7S / DX7II synthesizer patches — voices, performances, and extended voice data — stored in SysEx (`.syx`) files.

> **Performance note:** Designed to handle thousands of voices. All search and filtering is server-side with a 200-result limit; the frontend never loads the full dataset into memory.

---

## Overview

The DX7 Voice Browser scans a directory tree of `.syx` files, parses the binary MIDI System Exclusive (SysEx) format to extract individual patch names (voices, performances, extended voice data), stores them in a local SQLite database, and presents them through a searchable, retro-styled web UI. A collapsible folder tree lets you navigate your collection by directory structure, type filter pills isolate patch categories, and "Reveal in Explorer" jumps to any file instantly.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, [FastAPI](https://fastapi.tiangolo.com/) |
| Database | SQLite 3 (via Python's built-in `sqlite3` module) |
| Frontend | Vanilla HTML5 / CSS3 / JavaScript (ES2020, no framework) |
| Fonts | Google Fonts — Inter, Orbitron, Share Tech Mono |
| Icons | Font Awesome 6 |
| ASGI Server | Uvicorn (required to run FastAPI) |

---

## Project Structure

```
DX7_Voice_Browser/
├── app.py               # FastAPI backend — API routes and background scan runner
├── database.py          # SQLite helper — schema, CRUD operations
├── parser.py            # Binary SysEx parser — extracts voice names and positions
│
├── static/
│   ├── index.html       # Single-page application shell
│   ├── app.js           # Frontend logic — API calls, rendering, sorting, search
│   └── style.css        # Dark/retro theme — glassmorphism, LCD display, animations
│
├── sample_patches/      # Sample SysEx files for testing/demo
│   ├── ROM1A.syx        # DX7 ROM 1A factory bank (32 voices, headered)
│   ├── ROM1B.syx        # DX7 ROM 1B factory bank (32 voices, headered)
│   └── Classic/
│       └── DX7S_Bank.syx
│
├── test_parser.py       # Unit tests for parser.py (4 test cases)
├── verify_scanner.py    # Integration test — recursive directory scan end-to-end
│
└── voices.db            # SQLite database (auto-created on first run)
```

---

## Setup & Running

### Prerequisites

- Python 3.9+
- `pip` / virtual environment tooling

### Install Dependencies

```powershell
# Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install required packages
pip install fastapi uvicorn
```

> **Note:** The project has no `requirements.txt` yet. The only non-stdlib dependencies are `fastapi` and `uvicorn`.

### Run the Application

```powershell
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Then open your browser to: **http://127.0.0.1:8000**

---

## How to Use

1. **Enter a directory path** — Type an absolute Windows path to a folder containing `.syx` files (can be deeply nested).
2. **Click SCAN** — The backend walks the directory tree recursively, parses every `.syx` file, and populates the database. A progress bar and retro LCD panel show live status.
3. **Navigate with the folder tree** — A collapsible sidebar shows the hierarchy of all scanned folders. Click any node to filter the patch list to that folder and all subfolders. Click the same node again (or "ALL FOLDERS") to clear the filter. Use the tree icon button in the header to collapse/expand the sidebar.
4. **Filter by patch type** — Use the type pills above the table (ALL / VOICE / PERFORMANCE / GEN 2 EXT) to show only patches of a specific kind. Folder and type filters combine.
5. **Search patches** — Type in the filter box to instantly narrow results by patch name. Works together with folder and type filters.
6. **Sort columns** — Click Patch Name, Pos, Sysex File, or Files column headers to toggle ascending/descending sort.
7. **Browse grouped results** — The list shows **one row per unique (name, type) combination**. The **Type** column shows a colored badge (VOICE / PERF / GEN 2). The **Files** column shows how many `.syx` files contain that patch name.
8. **View duplicate files** — Click the teal Files badge on any row to open the **Duplicate Files** panel, which lists every file that contains that patch, with its bank position and folder path. Each entry has a Reveal button.
9. **Reveal in Explorer** — Click the folder icon on a main row or inside the duplicate panel to open Windows Explorer with that `.syx` file highlighted.
10. **Clear Database** — Removes all entries. The next scan starts fresh.
11. **Cleanup tab** — Click the **CLEANUP** tab to switch to the duplicate folder cleanup view. No rescan is needed — the analysis works from whatever is already in the database.
12. **Find duplicate folders** — Click **FIND DUPLICATES** to analyze the database and identify folders with identical `.syx` content (same filenames and same voices at the same positions).
13. **Choose which folder to keep** — Each duplicate group shows all matching folders. Select the one to keep using the radio button; the others are marked DEL.
14. **Delete duplicates** — Click **DELETE UNSELECTED** on a group to permanently delete the unselected folder(s) and all their contents from disk. A confirmation dialog lists exactly what will be removed. This action is irreversible.

---

## Functional Description

### Scanning Flow

```
User submits directory path
  → POST /api/scan
  → Background thread: os.walk() to find all *.syx files
  → For each file: parser.parse_syx_file()
  → Extracted voices batch-inserted into SQLite
  → Scan state updated (progress counters, current filename)

Frontend polls GET /api/scan-status every 500 ms
  → Updates LCD panel and progress bar
  → On completion: reloads voice list via GET /api/voices
```

### Search Flow

```
User types in search box
  → 300 ms debounce timer resets on each keystroke
  → Timer fires: GET /api/voices?q=<term>
  → SQLite: COUNT(*) + SELECT ... WHERE LIKE ? LIMIT 200
  → Returns { voices: [...], total: N }
  → Frontend sorts the returned page client-side and renders
  → Result counter shows "Showing 200 of 5,432 — refine to see more"
     or "42 voices found" when under the limit
```

### SysEx Parsing Logic (`parser.py`)

The parser scans every `.syx` file for Yamaha SysEx messages (`F0 43 0n <format_byte> ...`) and dispatches by format byte:

| Format byte | Type | `patch_type` stored |
|-------------|------|----------------------|
| `0x09` | VMEM — DX7 32-voice bulk dump | `"Voice"` |
| `0x7E` | PMEM — DX7II/DX7S performance bulk dump | `"Performance"` |
| `0x06` | AMEM — DX7II/DX7S additional voice bulk dump | `"Gen 2 Extended"` |
| *(none)* | Raw 4096-byte headerless dump | `"Voice"` |

**VMEM layout (existing DX7 format):**

| Offset | Size | Description |
|--------|------|-------------|
| 0 | 6 bytes | SysEx header: `F0 43 <ch> 09 20 00` |
| 6 | 4096 bytes | 32 voices × 128 bytes each |

Within each 128-byte voice block, bytes 118–127 hold the 10-byte ASCII voice name.

**PMEM (DX7II/DX7S Performance):** Body begins with a 10-byte `LM  8973PM` header, followed by 32 records of 51 bytes each. The 20-byte performance name starts at byte offset 31 within each record.

**AMEM (DX7II/DX7S Additional Voice Data):** 32 records of 35 bytes each, no name data. Synthetic names `Ext Voice 01`–`Ext Voice 32` are assigned to identify each slot. AMEM banks are often bundled in the same `.syx` file alongside a VMEM bank.

**Parser handles four cases:**
1. **Headered VMEM** — Scans for `F0 43 xx 09 20 00`; supports multiple banks concatenated in one file.
2. **Headered PMEM** — Scans for `F0 43 xx 7E`; skips 10-byte body header, extracts performance names.
3. **Headered AMEM** — Scans for `F0 43 xx 06`; stores synthetic slot names.
4. **Raw headerless dump** — If exactly 4096 bytes with no recognisable header, treats the whole file as a single VMEM bank.

---

## API Reference

All endpoints are served by FastAPI at `http://127.0.0.1:8000`.

### `POST /api/scan`
Start a background directory scan.

**Request body:**
```json
{ "directory": "C:\\Users\\you\\Music\\DX7_Patches" }
```

**Response:**
```json
{ "message": "Scan started." }
```

**Errors:** `400` if path is invalid or a scan is already running.

---

### `GET /api/scan-status`
Poll current scan progress.

**Response:**
```json
{
  "status": "scanning" | "idle",
  "files_scanned": 12,
  "total_files": 50,
  "current_file": "bank_xyz.syx",
  "voices_found": 384,
  "error": null
}
```

---

### `GET /api/folders`
Returns a sorted list of all unique folder paths currently indexed in the database. Used to populate the folder tree sidebar.

**Response:**
```json
[
  "C:\\Music\\DX7\\Factory",
  "C:\\Music\\DX7\\Factory\\ROM1",
  "C:\\Music\\DX7\\User"
]
```

---

### `GET /api/voices`
Fetch up to 200 **grouped** patches (one row per unique name + type combination), with optional filters.

**Query parameters:**
- `q` (optional): Case-insensitive substring filter on `voice_name` (SQLite `LIKE`)
- `folder` (optional): Show only patches from this folder path or any subfolder beneath it
- `patch_type` (optional): Exact match on patch type — `"Voice"`, `"Performance"`, or `"Gen 2 Extended"`

Results are grouped by `(voice_name, patch_type)` and sorted alphabetically. Returns at most `RESULT_LIMIT = 200` rows; use `total` to detect truncation.

**Response:**
```json
{
  "voices": [
    {
      "voice_name": "BASS 1",
      "patch_type": "Voice",
      "folder_path": "C:\\Music\\DX7_Patches\\Classic",
      "file_name": "ROM1A.syx",
      "file_path": "C:\\Music\\DX7_Patches\\Classic\\ROM1A.syx",
      "position": 3,
      "file_count": 4
    }
  ],
  "total": 1820
}
```

- `patch_type`: `"Voice"`, `"Performance"`, or `"Gen 2 Extended"`
- `file_count`: number of `.syx` files containing a patch with that name and type

---

### `GET /api/voices/files`

Fetch all individual records matching a patch name (and optionally a type). Used by the duplicate files panel.

**Query parameters:**
- `name` (required): Exact patch name to look up
- `patch_type` (optional): Limit to a specific type

**Response:**
```json
[
  {
    "voice_name": "BASS 1",
    "patch_type": "Voice",
    "folder_path": "C:\\Music\\DX7_Patches\\Classic",
    "file_name": "ROM1A.syx",
    "file_path": "C:\\Music\\DX7_Patches\\Classic\\ROM1A.syx",
    "position": 3
  }
]
```

Results are sorted by `file_name ASC, position ASC`. No row limit applies.

---

### `GET /api/duplicates`

Analyzes the database and returns groups of folders with identical `.syx` content sets. Two folders are considered duplicates when they contain exactly the same filenames and each file has the same 32 voices in the same positions.

**Response:**
```json
[
  {
    "fingerprint": "a3f9c2...",
    "folders": [
      {
        "folder_path": "C:\\Music\\DX7\\ROM",
        "file_count": 3,
        "example_file_path": "C:\\Music\\DX7\\ROM\\ROM1A.syx"
      },
      {
        "folder_path": "C:\\Backup\\DX7\\ROM",
        "file_count": 3,
        "example_file_path": "C:\\Backup\\DX7\\ROM\\ROM1A.syx"
      }
    ]
  }
]
```

Only groups with 2 or more folders are returned. An empty array means no duplicates were found.

---

### `POST /api/delete-folder`

Permanently deletes the entire directory tree for a given folder from disk and removes all matching records from the database.

**Request body:**
```json
{ "folder_path": "C:\\Backup\\DX7\\ROM" }
```

**Response:**
```json
{
  "deleted_path": "C:\\Backup\\DX7\\ROM",
  "had_indexed_subfolders": false,
  "error": null
}
```

- `had_indexed_subfolders`: `true` if the deleted folder contained subdirectories that were also indexed in the database (their records are removed too).
- `error`: `null` on success; an error message string if the filesystem deletion failed.

> ⚠️ **Irreversible**: Uses `shutil.rmtree` — the entire folder and all its contents are permanently deleted from disk.

---

### `POST /api/clear`
Delete all records from the database.

**Response:** `{ "message": "Database cleared successfully." }`

---

### `POST /api/reveal`
Open Windows Explorer with the specified file selected.

**Request body:**
```json
{ "file_path": "C:\\Music\\DX7_Patches\\Classic\\ROM1A.syx" }
```

**Response:** `{ "message": "Folder opened successfully." }`

**Errors:** `404` if file doesn't exist. `500` if Explorer fails to open.

> ⚠️ **Windows-only**: Uses `explorer /select,<path>`. Not portable to macOS/Linux without modification.

---

## Database Schema

**File:** `voices.db` (SQLite, created in the working directory on startup)

```sql
CREATE TABLE IF NOT EXISTS voices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_name  TEXT    NOT NULL,
    folder_path TEXT    NOT NULL,
    file_name   TEXT    NOT NULL,
    file_path   TEXT    NOT NULL,
    position    INTEGER NOT NULL,   -- 1-indexed within the bank/block (1–32)
    patch_type  TEXT    NOT NULL DEFAULT 'Voice'
);

CREATE INDEX IF NOT EXISTS idx_voice_name ON voices (voice_name);
```

The `patch_type` column is `"Voice"`, `"Performance"`, or `"Gen 2 Extended"`. Existing databases are migrated automatically via `ALTER TABLE` on first startup after upgrade.

**Result limit:** `database.RESULT_LIMIT = 200` — module-level constant controlling the maximum rows returned per query. Increase it if a higher browse limit is needed.

**Key database functions:**

- `get_all_folders()` — Returns a sorted list of unique `folder_path` values; used to populate the folder tree sidebar.
- `get_all_voices(search_query, folder_filter, type_filter)` — Grouped query (`GROUP BY voice_name, patch_type`) with optional text search, folder prefix filter, and patch type filter.
- `get_voices_by_name(voice_name, patch_type)` — Returns all individual records for a given name (and optionally type); used by the duplicate files panel.
- `get_duplicate_folder_groups()` — SHA-256 fingerprints each folder and returns groups with identical content.
- `delete_folder(folder_path)` — Removes DB records and deletes the directory tree via `shutil.rmtree`.

> The database is **cleared and repopulated on each scan** — it is not incremental/additive.

---

## Frontend Architecture (`static/`)

### `index.html`
Single-page HTML shell. No build step required. Sections:
- **Header** — Brand title + retro LCD status panel
- **Command Deck** — Directory input, SCAN button, progress bar, CLEAR DATABASE button
- **Tab Bar** — Toggles between PATCH EXPLORER and CLEANUP sections
- **Patch Explorer** — Header with tree toggle + type filter pills + sidebar (folder tree) + sortable results table
- **Cleanup** — Duplicate folder analysis: FIND DUPLICATES button, group cards with per-group DELETE UNSELECTED
- **Duplicate Files Modal** — Overlay listing all files that share a patch name
- **Toast** — Fixed-position notification overlay

### `app.js`
Plain ES2020 JavaScript. Key responsibilities:
- **`loadVoices(query)`** — Fetches patches from `/api/voices` with optional `q`, `folder`, and `patch_type` params; parses `{voices, total}` response
- **`loadFolders()`** — Fetches `/api/folders`, builds the folder tree via `buildFolderTree()`, and renders it with `renderFolderTree()`
- **`buildFolderTree(paths)`** — Converts a flat list of absolute paths into a nested tree object using path prefix matching
- **`renderFolderTree(node, container, depth)`** — Recursively renders tree nodes with expand/collapse chevrons; depth 0–1 expanded by default
- **`selectTreeFolder(path)`** — Sets `selectedFolder` and reloads the patch list; clicking the selected folder clears the filter
- **`toggleFolderTree()`** — Collapses/expands the sidebar by toggling `.collapsed` on `.folder-tree-panel`
- **`setTypeFilter(type)`** — Sets `selectedType` and reloads patches; type + folder filters combine
- **`handleScanTrigger()`** — POSTs to `/api/scan`, then starts polling
- **`startPollingStatus()`** — `setInterval` at 500ms; drives LCD and progress bar; reloads voices and folders on completion
- **`handleSearchInput()`** — Debounces 300ms then calls `loadVoices(query)` — filtering is fully server-side
- **`sortAndRender()`** — Sorts the server-returned page client-side and renders
- **`renderVoicesTable()`** — DOM-builds `<tr>` rows with Type badge; updates the result counter
- **`revealInExplorer()`** — POSTs to `/api/reveal`
- **`switchTab(tab)`** — Toggles visibility between PATCH EXPLORER and CLEANUP sections
- **`loadDuplicates()`** — Fetches `/api/duplicates` and renders results or empty state
- **`renderDuplicateGroups(groups)`** — Builds group cards with radio buttons and per-group delete button
- **`handleDeleteGroup(groupEl)`** — Confirms, POSTs `/api/delete-folder` for each unselected row, reloads
- **`showToast()`** — Auto-dismissing notification (4 s)

**State variables:**

| Variable | Purpose |
|----------|---------|
| `allVoices` | Current page of results from the server (≤ 200 items) |
| `filteredVoices` | Sorted view of `allVoices` used for rendering |
| `totalVoices` | Full matching count from `result.total` (may exceed 200) |
| `selectedFolder` | Currently selected folder path for the tree filter (`null` = all) |
| `selectedType` | Currently active type filter (`""` = all) |
| `treeOpen` | Whether the folder tree sidebar is visible |
| `expandedNodes` | `Set` of folder paths that are expanded in the tree |
| `searchDebounceTimer` | Timer ID for the 300ms search debounce |

### `style.css`
CSS custom properties design system with a dark, retro-synth theme:
- Color palette: teal (`hsl(172, 100%, 45%)`) + red accent on near-black (`hsl(225, 20%, 6%)`)
- Glassmorphism cards with `backdrop-filter: blur(12px)`
- Retro LCD panel: `Share Tech Mono` font + scanline overlay + glow text-shadow
- Animated ambient orb backgrounds
- Responsive layout (breakpoint at 768px)

---

## Testing

### Unit Tests — `test_parser.py`
Tests the `parser.py` module in isolation using synthetic SysEx data.

```powershell
python test_parser.py
```

| Test Case | Description |
|-----------|-------------|
| 1 | Standard 32-voice headered `.syx` |
| 2 | Raw 4096-byte headerless dump |
| 3 | Concatenated 2-bank file (64 voices) |
| 4 | Non-printable bytes are cleaned correctly |

### Integration Test — `verify_scanner.py`
Tests the full scan pipeline: directory walking → parsing → database insertion.
Creates a temporary nested folder structure with 3 mock banks, runs `run_background_scan()`, and verifies the database contents.

```powershell
python verify_scanner.py
```

Expected output: 96 voices across 3 banks at varying directory depths.

---

## Known Limitations & Notes

- **Windows-only** "Reveal in Explorer" feature (uses `explorer /select,<path>`).
- Scan is **destructive** — clearing and re-indexing on each run. There is no incremental/differential scan.
- The `scan_state` dictionary is an **in-process global** with no thread-locking (FastAPI background tasks use a thread pool, but the dictionary updates are simple assignments — adequate for single-user local use).
- Database path `voices.db` is **relative to the working directory** where `uvicorn` is launched.
- No authentication — intended for local single-user use only.
- The `bank_index` field returned by `parser.parse_syx_file()` is **not stored** in the database (only `position` within a bank is stored). If multiple banks exist in one file, patches from all banks are flattened with positions 1–32 repeated per bank.
- Search results are **capped at 200 rows** (`database.RESULT_LIMIT`). Column sorting applies only to the returned page, not the full dataset. Increase the constant if a higher browse limit is needed.
- **Folder deletion is irreversible** — the Cleanup tab uses `shutil.rmtree`, which permanently removes the entire directory and all its contents. There is no recycle bin or undo.
- Duplicate folder detection is based solely on **data in the current database**. If files have been added, moved, or deleted on disk since the last scan, re-scan before running Cleanup to get accurate results.
- **AMEM has no patch names** — Gen 2 Extended Voice slots are stored with synthetic names (`Ext Voice 01`–`Ext Voice 32`) since the AMEM format carries no name data. The VMEM bank paired with an AMEM bank (often in the same file) holds the actual voice names for those slots.

---

## Sample Patches

The `sample_patches/` directory contains original Yamaha factory bank files for quick testing:

| File | Contents |
|------|----------|
| `ROM1A.syx` | DX7 ROM Pack 1A — 32 factory voices |
| `ROM1B.syx` | DX7 ROM Pack 1B — 32 factory voices |
| `Classic/DX7S_Bank.syx` | DX7S classic bank — 32 voices |

To test: point the SCAN field at `<project_root>\sample_patches` and click SCAN.
