# Yamaha DX7 Voice Browser

A local web application for cataloging, searching, and locating Yamaha DX7 / DX7S / DX7II synthesizer patches — voices, performances, and extended voice data — stored in SysEx (`.syx`) files.

> **Performance note:** Designed to handle thousands of voices. All search and filtering is server-side with a 200-result limit; the frontend never loads the full dataset into memory.

---

## Overview

The DX7 Voice Browser scans a directory tree of `.syx` files, parses the binary MIDI System Exclusive (SysEx) format to extract individual patch names (voices, performances, extended voice data), stores them in a local SQLite database, and presents them through a searchable, retro-styled web UI. A collapsible folder tree lets you navigate your collection by directory structure, type filter pills isolate patch categories, and "Reveal in Explorer" jumps to any file instantly.

---

## Design System (read before any UI change)

This project follows a documented design system. **All UI work — by any
contributor or AI agent — must stay consistent with it.** Full spec:
[`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md);
tokens: [`static/tokens.css`](static/tokens.css); agent guardrails:
[`CLAUDE.md`](CLAUDE.md).

**Direction:** dark, techy, modern & bold — *calm by default, loud on purpose.*

### Non-negotiable rules

1. **Tokens only.** Reference `--ds-*` custom properties from `static/tokens.css`
   for every color, font, size, space, radius and shadow. Never hardcode a raw
   hex / px value — if a token is missing, add it to `tokens.css` first.
2. **Two fonts.** Space Grotesk (UI + display) and JetBrains Mono (all data:
   paths, positions, file names, counts, status). No third family.
3. **One accent.** `--ds-signal` (`#2fe3c2`) is the only brand/action color.
   The patch-type hues are data-only; red is destructive-only.
4. **No glow, no glass, no orbs.** Do not add `text-shadow`/`box-shadow` halos,
   `backdrop-filter: blur()`, or animated background elements. One subtle shadow
   is the only elevation.
5. **Respect the scale.** Type sizes 11–32px from the scale; spacing on a 4px
   grid; radius 6/10/14/999. Every interactive element gets a visible focus ring.

### Token quick reference

| Group | Values |
|---|---|
| Neutrals | bg `#0a0c0f` · sunken `#08090b` · surface `#101317` · elevated `#161a1f` · border `#242a31` / `#313942` |
| Text | `#eaedf0` · `#c0c7cd` · `#97a1aa` · `#5f6870` |
| Signal | `#2fe3c2` (ink on signal: `#06231d`) |
| Patch types | Voice `#2fe3c2` · Performance `#b58cff` · Gen 2 `#f5b860` |
| Status | success `#4fe09a` · warning `#f5b860` · danger `#ff5a6a` |
| Spacing | 4 / 8 / 12 / 16 / 24 / 32 / 48 / 72 |
| Radius | 6 ctrl · 10 card · 14 panel · 999 pill |

### Fonts (vendored — do not add a CDN `<link>`)

Space Grotesk and JetBrains Mono are served from `static/vendor/fonts/`, not from
Google Fonts. The packaged desktop app must work with no network, and a CDN
`<link>` silently degrades to fallback fonts (and, for Font Awesome, to blank
icons) for anyone offline.

```html
<link rel="stylesheet" href="vendor/fonts/fonts.css">
<link rel="stylesheet" href="vendor/fontawesome/css/all.min.css">
```

Regenerate with `toolsetch_vendor.ps1`; see
[`static/vendor/README.md`](static/vendor/README.md).

> `static/tokens.css` must load **before** `static/style.css`. It also aliases
> the legacy variable names, so loading it re-skins the app immediately; migrate
> `style.css` to the `--ds-*` names over time. Rollout order: P0 tokens → P1
> Patch Explorer → P2 Cleanup/modals → A11y (see DESIGN_SYSTEM.md §6).

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, [FastAPI](https://fastapi.tiangolo.com/) |
| Database | SQLite 3 (via Python's built-in `sqlite3` module) |
| Frontend | Vanilla HTML5 / CSS3 / JavaScript (ES2020, no framework) |
| Fonts | Space Grotesk, JetBrains Mono — vendored locally in `static/vendor/` |
| Icons | Font Awesome Free 6.4.0 — vendored locally in `static/vendor/` |
| ASGI Server | Uvicorn (required to run FastAPI) |
| Desktop shell | pywebview (WebView2) + PyInstaller, for the portable `.exe` |

---

## Project Structure

```
DX7_Voice_Browser/
├── main.py              # Desktop entry point — native window + embedded server
├── app.py               # FastAPI backend — API routes and background scan runner
├── database.py          # SQLite helper — schema, CRUD operations
├── parser.py            # Binary SysEx scanner — voice names/positions + raw byte blocks
├── voice_params.py      # Pure byte decoders — full voice parameters (see below)
├── paths.py             # All filesystem paths — bundled resources vs. writable user data
│
├── static/
│   ├── index.html       # Single-page application shell
│   ├── app.js           # Frontend logic — API calls, rendering, sorting, search
│   ├── style.css        # Dark, token-driven design system (see DESIGN_SYSTEM.md)
│   ├── tokens.css       # `--ds-*` design tokens — colors, type, spacing, radius
│   └── vendor/          # Offline copies of Font Awesome + the two fonts
│
├── sample_patches/      # Sample SysEx files, shipped as first-run demo data
│   ├── ROM1A.syx        # DX7 ROM 1A factory bank (32 voices, headered)
│   ├── ROM1B.syx        # DX7 ROM 1B factory bank (32 voices, headered)
│   └── Classic/
│       └── DX7S_Bank.syx
│
├── test_parser.py        # Unit tests for parser.py (4 test cases)
├── test_voice_params.py  # Unit tests for voice_params.py decoders + parser raw-block alignment
├── verify_scanner.py     # Integration test — recursive directory scan end-to-end
│
├── dx7_voice_browser.spec # PyInstaller build definition
├── requirements.txt       # Pinned runtime dependencies
├── requirements-dev.txt   # Runtime + PyInstaller, for building the .exe
├── assets/
│   ├── dx7.ico            # Application icon (generated by tools/make_icon.py)
│   └── version_info.txt   # Windows version resource
├── tools/
│   ├── fetch_vendor.ps1   # Regenerates static/vendor/ (occasional maintenance)
│   └── make_icon.py       # Regenerates assets/dx7.ico
│
├── DESIGN_SYSTEM.md      # Authoritative design system spec
├── CLAUDE.md             # Agent guardrails / architecture guide
└── start.ps1             # Dev flow — uvicorn with auto-reload in a browser
```

The SQLite database is **not** in the repo — it lives in
`%LOCALAPPDATA%\DX7VoiceBrowser\voices.db` (see `paths.py`).

---

## Install & Run (for users)

Download **`DX7VoiceBrowser.exe`** and double-click it. That's the whole install:
no Python, no terminal, no setup. It opens as a normal desktop window.

Two things to expect the first time:

- **"Windows protected your PC."** The app isn't code-signed (a certificate is a
  recurring annual cost), so SmartScreen warns about it. Click **More info →
  Run anyway**. You only have to do this once.
- **A few seconds before the window appears.** The app unpacks itself on each
  launch. Nothing is shown while that happens — if you double-click again,
  nothing bad happens, it just won't open a second window.

It needs the **Microsoft Edge WebView2 runtime**, which is already present on
Windows 11 and Windows 10 21H2 or newer. On the rare PC without it, the app says
so and links to Microsoft's free download.

### Where your files go

Nothing is written next to the `.exe`. Everything lives in
`%LOCALAPPDATA%\DX7VoiceBrowser\`:

| File | What it is |
| --- | --- |
| `voices.db` | The index of your scanned patches |
| `sample_patches\` | Demo patches, copied here on first run |
| `dx7browser.log` | Log file — attach this if you report a problem |
| `webview\` | Browser engine profile |

To uninstall, delete the `.exe` and that folder. Your `.syx` files are never
modified by scanning.

---

## Setup & Running (for development)

### Prerequisites

- Python 3.12+ (developed and built on 3.14)
- `pip` / virtual environment tooling
- Windows, for the desktop shell and Reveal-in-Explorer

### Install Dependencies

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1

# proxy_tools (a pywebview dependency) is published as an sdist only; it is
# pure Python. The --only-binary guard is there to stop pythonnet from
# attempting a source build, which would need MSVC and the .NET SDK.
pip install --only-binary=pythonnet,cffi -r requirements.txt
```

### Run the Application

Two entry points, sharing all the same code:

```powershell
# Desktop app — native window, ephemeral port, what end users get
python main.py

# Web/dev flow — auto-reload, fixed port, opened in your own browser
.\start.ps1        # then browse to http://127.0.0.1:8000
```

Use `python main.py` when changing anything about the window, the folder picker,
or startup; use `start.ps1` for ordinary front-end work, where auto-reload and
browser devtools are worth more. Set `DX7_DEBUG=1` to enable F12 devtools inside
the desktop window.

`DX7_DATA_DIR` overrides where the database and logs are kept, which is handy
for testing a first-run experience against a throwaway directory.

### Building the .exe

```powershell
py -3.14 -m venv .buildvenv
.\.buildvenv\Scripts\Activate.ps1
pip install --only-binary=pythonnet,cffi -r requirements-dev.txt

pyinstaller --noconfirm --clean dx7_voice_browser.spec   # -> dist\DX7VoiceBrowser.exe
```

Produces a single ~19 MB executable in `dist\`. **That is the one you ship.**

#### The two build variants

The spec builds either a windowed or a console executable from the same code and
the same bundled assets, chosen by the `DX7_BUILD_CONSOLE` environment variable
(`console=CONSOLE` in `dx7_voice_browser.spec`). The only real difference is the
Windows PE subsystem:

| | `dist\` (default) | `dist-console\` |
| --- | --- | --- |
| PE subsystem | GUI (2) | Console (3) |
| Console window | none | a terminal opens alongside the app |
| `sys.stdout` / `sys.stderr` | **`None`** | real streams |
| Use it for | shipping | debugging |

```powershell
$env:DX7_BUILD_CONSOLE = "1"
pyinstaller --noconfirm --clean --distpath dist-console dx7_voice_browser.spec
Remove-Item Env:\DX7_BUILD_CONSOLE
```

**Build the console variant first whenever something is wrong.** In the windowed
build `sys.stdout` and `sys.stderr` are `None`, so a crash before the window
opens produces nothing at all — no message, no window, no output; the app simply
fails to start. The console variant shows the traceback and pywebview's own
startup lines (`[pywebview] Using WinForms / Chromium … loaded event fired`),
which is usually enough to identify a missing hidden import or data file.

Never ship the console build: users would see a stray terminal window next to the
app and assume it is broken.

For problems reported by users, start with the log file instead —
`%LOCALAPPDATA%\DX7VoiceBrowser\dx7browser.log` records the same startup detail.
The windowed build is not blind, it just cannot use stdout; `main.py` passes
`log_config=None` to uvicorn precisely so it does not try to.

`tools\fetch_vendor.ps1` regenerates the offline copies of Font Awesome and the
two fonts in `static\vendor\`; `tools\make_icon.py` regenerates `assets\dx7.ico`.
Both are occasional maintenance steps — their output is committed, so a normal
build needs no network.

---

## How to Use

1. **Select a directory** — Type an absolute Windows path directly into the input field, or click the **folder icon** (Browse button) to open a native Windows folder picker and select the target folder.
2. **Click SCAN** — The backend walks the directory tree recursively, parses every `.syx` file, and populates the database. A progress bar and retro LCD panel show live status.
3. **Navigate with the folder tree** — A collapsible sidebar shows the hierarchy of all scanned folders. Click any node to filter the patch list to that folder and all subfolders. Click the same node again (or "ALL FOLDERS") to clear the filter. Use the tree icon button in the header to collapse/expand the sidebar.
4. **Filter by patch type** — Use the type pills above the table (ALL / VOICE / PERFORMANCE / GEN 2 EXT) to show only patches of a specific kind. Folder and type filters combine.
5. **Search patches** — Type in the filter box to instantly narrow results by patch name. Works together with folder and type filters.
6. **Sort columns** — Click Patch Name, Pos, Sysex File, or Files column headers to toggle ascending/descending sort.
7. **Browse grouped results** — The list shows **one row per unique (name, type) combination**. The **Type** column shows a colored badge (VOICE / PERF / GEN 2). The **Files** column shows how many `.syx` files contain that patch name.
8. **View duplicate files** — Click the teal Files badge on any row to open the **Duplicate Files** panel, which lists every file that contains that patch, with its bank position and folder path. Each entry has a Reveal button.
9. **Reveal in Explorer** — Click the folder icon on a main row or inside the duplicate panel to open Windows Explorer with that `.syx` file highlighted.
10. **View voice parameters** — Click the (i) icon next to a Voice or Gen 2 Extended row (or a duplicate-files modal entry) to open the full-page **Voice Parameters** view — every operator, envelope, LFO, and (for Gen 2 Extended patches) key mode / pitch bend / portamento / controller setting. Not shown for Performance rows, since a performance isn't a single voice. Click **BACK** to return to whichever tab you were on.
11. **Clear Database** — Removes all entries. The next scan starts fresh.
12. **Cleanup tab** — Click the **CLEANUP** tab to switch to the duplicate folder cleanup view. No rescan is needed — the analysis works from whatever is already in the database.
13. **Find duplicate folders** — Click **FIND DUPLICATES** to identify folders whose `.syx` files are **byte-for-byte identical**. Files are read from disk and hashed (SHA-256), so an edited copy of a bank is *not* treated as a duplicate of the original even when every patch name matches.
14. **Choose which folder to keep** — Each duplicate group shows all matching folders. Select the one to keep using the radio button; the others are marked DEL.
15. **Delete duplicates** — Click **DELETE UNSELECTED** on a group to permanently delete the unselected folder(s) and all their contents from disk. A confirmation dialog lists exactly what will be removed. This action is irreversible.

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

### Voice Parameters Flow

```
User clicks the (i) "View Details" button on a voice row (or a duplicate-files
modal entry) — hidden for Performance rows
  → GET /api/voices/{id}/parameters
  → Backend re-reads the source .syx file (parser.extract_voice_blocks()),
    locates the exact voice by occurrence index (see below), and decodes it
    (voice_params.build_voice_parameters())
  → Frontend renders the full-page Voice Parameters view: 6 operators (with
    envelope graphs), LFO, Pitch EG, and — for Gen 2 Extended patches — key
    mode, pitch bend/portamento, and controller routing (BC/AT/MW/FC1/FC2/MIDI)
  → Plain "Voice" patches show the documented power-on defaults for the
    Gen-2-only sections (no $06 data exists for them at all), visually marked
    as defaults (muted, italic values + a "DEFAULT VALUES" tag)
```

**Locating a specific voice's raw bytes:** the database stores no raw SysEx
bytes and no bank index — only name/position/patch_type/file location. Since
`parser.parse_syx_file()` is a pure function of a file's bytes and always
returns voices in the same order, a DB row's 0-based rank among all other rows
sharing its `file_path` (ordered by `id ASC`) is exactly that voice's index in
a fresh call to `parser.extract_voice_blocks()` for the same file — see
`database.get_voice_occurrence_index()`. No schema migration was needed to add
this feature.

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

**AMEM (DX7II/DX7S Additional Voice Data):** 32 records of 35 bytes each, no name data. Synthetic names `Ext Voice 01`–`Ext Voice 32` are assigned initially, then resolved by the merge step below.

**VMEM + AMEM merge (`_merge_vmem_amem`):** The DX7S and DX7II store VMEM and AMEM banks in the same `.syx` file — the synth always loads them together as a single Gen 2 Voice. When both are present, the parser merges each matched pair by `(bank_index, position)`: the resulting entry gets the `patch_type` `"Gen 2 Extended"` and the voice name from the VMEM slot. Unmatched VMEM voices keep their original type; unmatched AMEM slots keep their synthetic name.

**Parser handles four cases:**

1. **Headered VMEM** — Scans for `F0 43 xx 09 20 00`; supports multiple banks concatenated in one file.
2. **Headered PMEM** — Scans for `F0 43 xx 7E`; skips 10-byte body header, extracts performance names.
3. **Headered AMEM** — Scans for `F0 43 xx 06`; assigns synthetic slot names, then merges with any VMEM bank in the same file.
4. **Raw headerless dump** — If exactly 4096 bytes with no recognisable header, treats the whole file as a single VMEM bank.

Internally, `parser.py` scans and merges VMEM/AMEM/PMEM messages through one
shared function, `_scan_all_patches()`. `parse_syx_file()` (used by the scan
flow above) returns just names/positions from it; `extract_voice_blocks()`
(used by the Voice Parameters flow) returns the same list in the same order,
but keeps the raw `_core_bytes` (128-byte VMEM record) / `_additional_bytes`
(35-byte AMEM record) for each voice so they can be fully decoded.

### Full Voice Parameter Decoding (`voice_params.py`)

A separate, pure module (no file I/O) turns those raw byte blocks into every
synthesis parameter — reusable by any future feature that needs full voice
data (export, comparison, editing, etc.), independent of how the bytes were
found in a file.

| Function | Purpose |
|----------|---------|
| `decode_core_voice(core_bytes)` | Decodes a 128-byte VMEM record: algorithm, feedback, oscillator key sync, transpose, LFO, pitch EG, and all 6 operators (re-ordered from the on-disk OP6→OP1 storage order to logical OP1→OP6) |
| `decode_additional_voice(additional_bytes)` | Decodes a 35-byte AMEM record: per-operator scaling mode/AM sensitivity, pitch EG range/velocity/rate-scaling, key mode & unison, pitch bend, portamento, and all 6 controller routings (BC/AT/MW/FC1/FC2/MIDI). Pass `None` (plain DX7 mkI voices have no AMEM block) to get the documented power-on defaults instead, with `"present": False` |
| `build_voice_parameters(core_bytes, additional_bytes)` | Combines both into the full parameter model returned by the API |
| `DX7_ALGORITHMS` | Static reference table: which operators are carriers vs modulators, and which one carries feedback, per algorithm 1–32 — drives the operator dot coloring/feedback icon on the Voice Parameters page. **Not** derived from the sysex bytes (the format only stores the algorithm *number*); reconstructed from general DX7 reference knowledge and only spot-checked against algorithm 2 (see Known Limitations) |

Byte offsets and bit layouts follow
`design_handoff_voice_parameters/yamaha_dx7s_sysex_specification_v2_1.md`
sections 5 (core voice) and 6 (additional voice) exactly; see that file for the
full byte-by-byte reference.

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

### `GET /api/browse-folder`

Opens a native OS folder picker dialog (Windows: `tkinter.filedialog.askdirectory`) on the server and returns the path the user selected. Used by the Browse button next to the scan input.

**Response:**

```json
{ "path": "C:/Users/you/Music/DX7_Patches" }
```

Returns `{ "path": null }` if the user cancels the dialog without selecting a folder.

> **Windows-only**: Uses Python's `tkinter` standard library. The dialog appears on top of the browser window. No external dependencies are required.

---

### `GET /api/folders`

Returns a sorted list of all unique folder paths currently indexed in the database. Used to populate the folder tree sidebar.

**Response:**

```json
[
  "C:/Music/DX7/Factory",
  "C:/Music/DX7/Factory/ROM1",
  "C:/Music/DX7/User"
]
```

> **Note:** Paths are stored internally with forward slashes `/` regardless of OS, so all path values returned by the API use forward slashes.

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
      "id": 42,
      "voice_name": "BASS 1",
      "patch_type": "Voice",
      "folder_path": "C:/Music/DX7_Patches/Classic",
      "file_name": "ROM1A.syx",
      "file_path": "C:/Music/DX7_Patches/Classic/ROM1A.syx",
      "position": 3,
      "file_count": 4
    }
  ],
  "total": 1820
}
```

- `id`: the primary key of one representative row for this `(voice_name, patch_type)`
  group (the lowest `id` among matches) — pass it to
  `GET /api/voices/{id}/parameters` to view its full synthesis parameters.
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
    "id": 42,
    "voice_name": "BASS 1",
    "patch_type": "Voice",
    "folder_path": "C:/Music/DX7_Patches/Classic",
    "file_name": "ROM1A.syx",
    "file_path": "C:/Music/DX7_Patches/Classic/ROM1A.syx",
    "position": 3
  }
]
```

Results are sorted by `file_name ASC, position ASC`. No row limit applies.
Each entry's `id` can be passed to `GET /api/voices/{id}/parameters` — this is
what powers the "View Details" button inside the duplicate-files modal.

---

### `GET /api/voices/{voice_id}/parameters`

Returns the fully decoded synthesis parameters for a single voice, re-read from
its source `.syx` file (see [Voice Parameters Flow](#voice-parameters-flow) and
[`voice_params.py`](#full-voice-parameter-decoding-voice_paramspy) above).

**Response** (trimmed — every operator has the full field set shown for OP1):

```json
{
  "id": 42,
  "voice_name": "BASS 1",
  "patch_type": "Gen 2 Extended",
  "folder_path": "C:/Music/DX7_Patches/Classic",
  "file_name": "ROM1A.syx",
  "file_path": "C:/Music/DX7_Patches/Classic/ROM1A.syx",
  "position": 3,
  "name": "BASS 1",
  "algorithm": 2,
  "algorithm_carriers": [1, 2],
  "algorithm_feedback_op": 2,
  "feedback": 7,
  "osc_key_sync": true,
  "transpose": 12,
  "transpose_name": "C2",
  "operators": [
    {
      "op": 1,
      "eg_rate": [54, 35, 19, 60], "eg_level": [99, 97, 94, 0],
      "break_point": 0, "break_point_name": "A-1",
      "left_depth": 0, "right_depth": 0,
      "left_curve": 0, "left_curve_name": "-LIN",
      "right_curve": 0, "right_curve_name": "-LIN",
      "rate_scaling": 2, "detune": 0,
      "amp_mod_sens": 0, "vel_sens": 1,
      "level": 97, "osc_mode": "Ratio", "freq_coarse": 1, "freq_fine": 0
    }
  ],
  "pitch_eg": { "rate": [99, 95, 95, 99], "level": [50, 48, 50, 50] },
  "lfo": {
    "speed": 30, "delay": 0, "pmd": 0, "amd": 0, "sync": false,
    "wave": 0, "wave_name": "TRI", "pitch_mod_sensitivity": 2
  },
  "additional": {
    "present": true,
    "key_mode_assign": "Polyphonic",
    "unison_detune": 0,
    "pitch_bend_range": 2, "pitch_bend_step": 0, "pitch_bend_mode": "Normal",
    "portamento_mode": "Sus-Key/Retain-Follow", "portamento_time": 0, "portamento_step": 0,
    "random_pitch": 2,
    "mod_wheel": { "pitch": 31, "amp": 0, "eg_bias": 0 },
    "breath_controller": { "pitch": 0, "amp": 0, "eg_bias": 0, "pitch_bias": 0 },
    "aftertouch": { "pitch": 0, "amp": 0, "eg_bias": 63, "pitch_bias": 0 },
    "foot_controller_1": { "pitch": 0, "amp": 0, "eg_bias": 0, "volume": 0 },
    "foot_controller_2": { "pitch": 0, "amp": 0, "eg_bias": 0, "volume": 99 },
    "midi_controller": { "pitch": 0, "amp": 0, "eg_bias": 0, "volume": 0 },
    "fc1_as_cs1": false
  }
}
```

- `algorithm_carriers` / `algorithm_feedback_op`: which operators are wired to
  the audio output and which one carries the feedback loop for this
  `algorithm`, from `voice_params.DX7_ALGORITHMS` (see the caveat about this
  table in Known Limitations).
- `additional.present`: `true` for `"Gen 2 Extended"` patches (real `$06` data
  was decoded); `false` for plain `"Voice"` patches — in that case every field
  under `additional` holds the documented power-on default from spec §6, not
  data actually stored in the voice. The frontend shows these visually muted.

**Errors:**

- `404` — no voice with this `id`.
- `400` — `patch_type` is `"Performance"` (not a single voice; not applicable).
- `409` — the source `.syx` file couldn't be re-read or no longer matches what
  was scanned (moved/edited/deleted since the last scan) — re-scan its folder.

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
        "folder_path": "C:/Music/DX7/ROM",
        "file_count": 3,
        "example_file_path": "C:/Music/DX7/ROM/ROM1A.syx"
      },
      {
        "folder_path": "C:/Backup/DX7/ROM",
        "file_count": 3,
        "example_file_path": "C:/Backup/DX7/ROM/ROM1A.syx"
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
  "deleted_path": "C:/Backup/DX7/ROM",
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
- **`buildFolderTree(paths)`** — Converts a flat list of absolute paths into a nested tree object; creates intermediate nodes for every path segment (not just leaf DB paths), so the full hierarchy is visible even for folders that hold only subfolders. Finds the deepest common ancestor as the tree root.
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
- **`showVoiceDetail(id)`** — Fetches `/api/voices/{id}/parameters`, hides the current tab, shows `#section-detail`, and calls `renderVoiceDetail()`; reverts to the previous tab and toasts on error
- **`backFromDetail()`** — Returns from the Voice Parameters view to whichever tab (Explorer/Cleanup) was active before
- **`renderVoiceDetail(data)`** — Builds the header (name, patch-type badge, algorithm mini-diagram, key-stat strip), the 6 operator tiles, LFO + Pitch EG cards, and the Key Mode/Pitch Bend/Controllers sections; the latter get a muted "DEFAULT VALUES" tag when `data.additional.present` is `false`
- **`envSvg(rates, levels, opts)` / `waveSvg(shape, opts)`** — Draw the DX7 envelope contour / LFO waveform as an inline SVG markup string; ported from `design_handoff_voice_parameters/Voice Parameters Page.dc.html`'s reference logic (same geometry, no framework)

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
| `searchDebounceTimer` | Timer ID for the search debounce |
| `voicesAbortController` | `AbortController` used to cancel an in-flight `/api/voices` request when a newer one is triggered |
| `statusInterval` | `setInterval` handle for the scan-status polling loop; cleared on completion or page unload |

### `style.css` / `tokens.css`

Dark, flat, token-driven design system — see [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md)
for the full spec. `tokens.css` defines every `--ds-*` custom property (colors,
type, spacing, radius, shadow) and must load before `style.css`. Highlights:

- One brand accent (`--ds-signal`, teal `#2fe3c2`); patch-type hues (Voice/
  Performance/Gen 2) are for data badges only, never decoration
- Two fonts only: Space Grotesk (UI/display) and JetBrains Mono (all data —
  paths, positions, file names, counts, status)
- **No** glow, glass (`backdrop-filter: blur()`), or animated background
  elements — one subtle shadow (`--ds-shadow` / `--ds-shadow-lg`) is the only
  elevation
- Spacing on a 4px grid, radius from a fixed scale (6/10/14/999)
- Responsive layout (breakpoints around 768–900px)

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

### Unit Tests — `test_voice_params.py`

Tests `voice_params.py`'s decoders and the `parser.py` raw-block extraction path.

```powershell
python test_voice_params.py
```

| Test | Description |
|------|--------------|
| `test_decode_core_voice` | Decodes a synthetic 128-byte core voice against the spec's own worked example (algorithm, feedback, transpose, LFO) and asserts every OP1 bitfield, including the OP6→OP1 storage-order reversal |
| `test_decode_additional_voice_present` | Decodes a synthetic 35-byte AMEM record (key mode, pitch bend range, controller bias fields) |
| `test_decode_additional_voice_defaults` | Confirms `decode_additional_voice(None)` returns the documented power-on defaults with `present: False` |
| `test_build_voice_parameters` | Confirms core + additional combine correctly, with and without an additional block |
| `test_extract_voice_blocks_matches_parse_syx_file` | Confirms `extract_voice_blocks()` and `parse_syx_file()` return identical name/position/patch_type ordering for the same file — this is what lets a DB row's rank map onto the right voice (see `database.get_voice_occurrence_index`) |

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
- Database path is `%LOCALAPPDATA%\DX7VoiceBrowser\voices.db`, resolved by `paths.py` and independent of the working directory. Override it with the `DX7_DATA_DIR` environment variable.
- No authentication — intended for local single-user use only.
- The `bank_index` field returned by `parser.parse_syx_file()` is **not stored** in the database (only `position` within a bank is stored). If multiple banks exist in one file, patches from all banks are flattened with positions 1–32 repeated per bank.
- Search results are **capped at 200 rows** (`database.RESULT_LIMIT`). Column sorting applies only to the returned page, not the full dataset. Increase the constant if a higher browse limit is needed.
- **Folder deletion is irreversible** — the Cleanup tab uses `shutil.rmtree`, which permanently removes the entire directory and all its contents. There is no recycle bin or undo.
- Duplicate folder detection reads and hashes the `.syx` files **on disk**, using the database only to know which folders to look at. Folders that no longer exist, or whose files cannot be read, are skipped rather than being reported as duplicates. A folder added since the last scan will not be considered until you re-scan.
- **AMEM has no patch names** — The AMEM format carries no name data. When a VMEM bank is bundled in the same file (the common DX7S/DX7II case), names are taken from the paired VMEM slots after merging. If an AMEM bank arrives without a paired VMEM, synthetic names `Ext Voice 01`–`Ext Voice 32` are kept.
- **`DX7_ALGORITHMS` (in `voice_params.py`) needs verification** — the carrier/
  modulator/feedback-operator table used to color the Voice Parameters page's
  operator tiles is reconstructed from general DX7 reference knowledge, not
  from the sysex byte spec (which never stores per-algorithm routing). Only
  algorithm 2 has been cross-checked against a real worked example; spot-check
  the remaining 31 entries against the official Yamaha DX7 algorithm chart
  before relying on it beyond this page's decorative coloring.
- **Voice Parameters requires the source file to still match the last scan** —
  the detail endpoint re-reads the `.syx` file rather than storing raw bytes
  in the database (see Voice Parameters Flow above). If a file was moved,
  edited, or deleted since scanning, opening its details returns a `409` and
  a "re-scan this folder" toast instead of stale or incorrect data.

---

## Sample Patches

The `sample_patches/` directory contains original Yamaha factory bank files for quick testing:

| File | Contents |
|------|----------|
| `ROM1A.syx` | DX7 ROM Pack 1A — 32 factory voices |
| `ROM1B.syx` | DX7 ROM Pack 1B — 32 factory voices |
| `Classic/DX7S_Bank.syx` | DX7S classic bank — 32 voices |

To test: point the SCAN field at `<project_root>\sample_patches` and click SCAN.

These are also bundled into the packaged app. On first run they are copied to
`%LOCALAPPDATA%\DX7VoiceBrowser\sample_patches\` and indexed automatically, so a
new user sees real data immediately, and the scan field is prefilled with that
path. Seeding is skipped if the database already holds patches, and never
repeats once it has run — including after **Clear Database**.

---

## Third-Party Assets

Fonts and icons are vendored in `static/vendor/` so the packaged app works
offline. See [`static/vendor/README.md`](static/vendor/README.md) for versions
and regeneration steps.

- **Font Awesome Free 6.4.0** — icons [CC BY 4.0](https://fontawesome.com/license/free),
  fonts SIL OFL 1.1, code MIT. © Fonticons, Inc.
- **Space Grotesk** — SIL OFL 1.1. © Florian Karsten.
- **JetBrains Mono** — SIL OFL 1.1. © JetBrains s.r.o.
