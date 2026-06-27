# Yamaha DX7 Voice Browser

A local web application for cataloging, searching, and locating Yamaha DX7 / DX7S synthesizer patch voices stored in SysEx (`.syx`) files.

> **Performance note:** Designed to handle thousands of voices. All search and filtering is server-side with a 200-result limit; the frontend never loads the full dataset into memory.

---

## Overview

The DX7 Voice Browser scans a directory tree of `.syx` files, parses the binary MIDI System Exclusive (SysEx) format to extract individual voice (patch) names, stores them in a local SQLite database, and presents them through a searchable, retro-styled web UI. A "Reveal in Explorer" action lets you instantly jump to the containing folder of any patch.

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
3. **Search voices** — Type in the filter box to instantly narrow results by voice name.
4. **Sort columns** — Click Voice Name, Pos, Sysex File, or Files column headers to toggle ascending/descending sort.
5. **Browse grouped results** — The list shows **one row per unique voice name**. The **Files** column shows how many `.syx` files contain that voice name. A teal badge with a stack icon indicates duplicates; a grey badge indicates a single file.
6. **View duplicate files** — Click the teal Files badge on any row to open the **Duplicate Files** panel, which lists every file that contains that voice, with its bank position and folder path. Each entry has a Reveal button.
7. **Reveal in Explorer** — Click the folder icon on a main row (reveals the representative file) or inside the duplicate panel (reveals the specific file) to open Windows Explorer with that `.syx` file highlighted.
8. **Clear Database** — Removes all entries. The next scan starts fresh.

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

The DX7 uses a well-documented **32-voice bulk dump** binary format:

| Offset | Size | Description |
|--------|------|-------------|
| 0 | 6 bytes | SysEx header: `F0 43 <ch> 09 20 00` |
| 6 | 4096 bytes | 32 voices × 128 bytes each |
| 4102 | 1 byte | Checksum |
| 4103 | 1 byte | `F7` (End of SysEx) |

**Within each 128-byte voice block:**
- Bytes 0–117: Operator parameters (6 operators × ~17 bytes + algorithm/global params)
- Bytes 118–127: **Voice name** (10 ASCII bytes, 7-bit MIDI data)

**Parser handles three cases:**
1. **Standard headered file** — Scans for the `F0 43 xx 09 20 00` signature; supports multiple banks concatenated in a single file (multi-bank `.syx`).
2. **Raw headerless dump** — If the file is exactly 4096 bytes with no header found, treats the whole file as a single bank.
3. **Non-printable byte cleanup** — Characters outside ASCII 32–126 are replaced with spaces; resulting name is stripped.

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

### `GET /api/voices?q=<query>`
Fetch up to 200 **grouped** voices (one row per unique name), optionally filtered.

- `q` (optional): Case-insensitive substring filter on `voice_name` (SQLite `LIKE`)
- Results are grouped by `voice_name` and sorted alphabetically
- Always returns at most `RESULT_LIMIT = 200` unique names; use `total` to detect truncation
- `file_count` indicates how many individual records share that name

**Response:**
```json
{
  "voices": [
    {
      "voice_name": "BASS 1",
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

- `voices`: up to 200 grouped records (one per unique name)
- `total`: full count of **unique** voice names matching the query
- `file_count`: number of `.syx` files that contain a voice with this name

---

### `GET /api/voices/files?name=<voice_name>`

Fetch all individual records that share the given exact voice name. Used by the duplicate files panel.

- `name` (required): Exact voice name to look up

**Response:**
```json
[
  {
    "voice_name": "BASS 1",
    "folder_path": "C:\\Music\\DX7_Patches\\Classic",
    "file_name": "ROM1A.syx",
    "file_path": "C:\\Music\\DX7_Patches\\Classic\\ROM1A.syx",
    "position": 3
  },
  {
    "voice_name": "BASS 1",
    "folder_path": "C:\\Music\\DX7_Patches\\ROM",
    "file_name": "ROM1B.syx",
    "file_path": "C:\\Music\\DX7_Patches\\ROM\\ROM1B.syx",
    "position": 7
  }
]
```

Results are sorted by `file_name ASC, position ASC`. No row limit applies.

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
    position    INTEGER NOT NULL   -- 1-indexed position within the SysEx bank (1–32)
);

CREATE INDEX IF NOT EXISTS idx_voice_name ON voices (voice_name);
```

The index makes `LIKE '%term%'` searches fast even with tens of thousands of rows.

**Result limit:** `database.RESULT_LIMIT = 200` — module-level constant controlling the maximum rows returned per query. Increase it if a higher browse limit is needed.

> The database is **cleared and repopulated on each scan** — it is not incremental/additive.

---

## Frontend Architecture (`static/`)

### `index.html`
Single-page HTML shell. No build step required. Sections:
- **Header** — Brand title + retro LCD status panel
- **Command Deck** — Directory input, SCAN button, progress bar, CLEAR DATABASE button
- **Patch Explorer** — Search input + sortable results table + empty/loading states
- **Toast** — Fixed-position notification overlay

### `app.js`
Plain ES2020 JavaScript. Key responsibilities:
- **`loadVoices(query)`** — Fetches voices from `/api/voices?q=<query>` (or unfiltered on page load); parses `{voices, total}` response
- **`handleScanTrigger()`** — POSTs to `/api/scan`, then starts polling
- **`startPollingStatus()`** — `setInterval` at 500ms; drives LCD and progress bar updates; reloads voices on completion
- **`handleSearchInput()`** — Debounces 300ms then calls `loadVoices(query)` — filtering is fully server-side
- **`sortAndRender()`** — Sorts the current server-returned page client-side and renders (replaced the old `applyFilterAndRender`)
- **`renderVoicesTable()`** — DOM-builds `<tr>` rows; updates the result counter ("Showing X of Y" when capped)
- **`revealInExplorer()`** — POSTs to `/api/reveal`
- **`showToast()`** — Auto-dismissing notification (4 s)

**State variables:**

| Variable | Purpose |
|----------|---------|
| `allVoices` | Current page of results from the server (≤ 200 items) |
| `filteredVoices` | Sorted view of `allVoices` used for rendering |
| `totalVoices` | Full matching count from `result.total` (may exceed 200) |
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
- The `bank_index` field returned by `parser.parse_syx_file()` is **not stored** in the database (only `position` within a bank is stored). If multiple banks exist in one file, voices from all banks are flattened with positions 1–32 repeated per bank.
- Search results are **capped at 200 rows** (`database.RESULT_LIMIT`). Column sorting applies only to the returned page, not the full dataset. Increase the constant if a higher browse limit is needed.

---

## Sample Patches

The `sample_patches/` directory contains original Yamaha factory bank files for quick testing:

| File | Contents |
|------|----------|
| `ROM1A.syx` | DX7 ROM Pack 1A — 32 factory voices |
| `ROM1B.syx` | DX7 ROM Pack 1B — 32 factory voices |
| `Classic/DX7S_Bank.syx` | DX7S classic bank — 32 voices |

To test: point the SCAN field at `<project_root>\sample_patches` and click SCAN.
