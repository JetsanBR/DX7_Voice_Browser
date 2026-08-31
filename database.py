import sqlite3
import os
import hashlib
import json
import shutil
from contextlib import closing

import paths

# Absolute path, so the database is found no matter what the working directory
# is. _connect() reads this as a module global at call time and every query
# function goes through _connect(), so this one assignment reroutes them all.
DB_FILE = str(paths.db_path())
RESULT_LIMIT = 200


def _connect():
    """Opens a DB connection with Row factory enabled."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database schema and indexes if they don't exist."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voice_name TEXT NOT NULL,
                folder_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                position INTEGER NOT NULL,
                patch_type TEXT NOT NULL DEFAULT 'Voice'
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_voice_name ON voices (voice_name)"
        )
        conn.commit()
        # Migrate databases that pre-date the patch_type column
        cursor.execute("PRAGMA table_info(voices)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'patch_type' not in columns:
            cursor.execute(
                "ALTER TABLE voices ADD COLUMN patch_type TEXT NOT NULL DEFAULT 'Voice'"
            )
            conn.commit()


def clear_db():
    """Clears all records from the database."""
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM voices")
        conn.commit()


def count_voices():
    """Total number of indexed patches. Used to tell a first run apart from an
    existing install, since scanning is destructive (it calls clear_db first)."""
    with closing(_connect()) as conn:
        return conn.execute("SELECT COUNT(*) FROM voices").fetchone()[0]


def insert_voices(voices):
    """
    Inserts a list of patch records (voices, performances, etc.).
    Each dict must have: voice_name, folder_path, file_name, file_path, position, patch_type.
    Paths are expected to use forward slashes (normalized by the caller).
    """
    if not voices:
        return
    with closing(_connect()) as conn:
        conn.executemany("""
            INSERT INTO voices (voice_name, folder_path, file_name, file_path, position, patch_type)
            VALUES (:voice_name, :folder_path, :file_name, :file_path, :position, :patch_type)
        """, voices)
        conn.commit()


def get_all_voices(search_query=None, folder_filter=None, type_filter=None):
    """
    Fetches up to RESULT_LIMIT patches grouped by (voice_name, patch_type), sorted
    alphabetically. Supports optional text search, folder prefix filter, and type filter.
    Returns: { "voices": [...], "total": <int> }
    """
    conditions, params = [], []
    if search_query:
        conditions.append("voice_name LIKE ?")
        params.append(f"%{search_query}%")
    if folder_filter:
        # Normalize to forward slashes — paths in DB are stored with /
        folder_norm = folder_filter.replace('\\', '/')
        conditions.append("(folder_path = ? OR folder_path LIKE ?)")
        params.extend([folder_norm, folder_norm + '/%'])
    if type_filter:
        conditions.append("patch_type = ?")
        params.append(type_filter)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT COUNT(DISTINCT voice_name || '|' || patch_type) FROM voices {where}",
            params
        )
        total = cursor.fetchone()[0]

        cursor.execute(
            f"""
            SELECT
                MIN(id) AS id,
                voice_name,
                patch_type,
                folder_path,
                file_name,
                file_path,
                position,
                COUNT(*) AS file_count
            FROM voices
            {where}
            GROUP BY voice_name, patch_type
            ORDER BY voice_name ASC
            LIMIT ?
            """,
            params + [RESULT_LIMIT]
        )
        rows = cursor.fetchall()

    return {"voices": [dict(row) for row in rows], "total": total}


def get_all_folders():
    """Returns a sorted list of unique folder paths currently indexed in the database."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT folder_path FROM voices ORDER BY folder_path ASC")
        return [row[0] for row in cursor.fetchall()]


def get_voices_by_name(voice_name: str, patch_type: str = None):
    """
    Returns all individual records that share the given voice_name (and optionally patch_type).
    Used by the "duplicate files" modal to show every file containing a patch with that name.
    Returns: list of dicts with voice_name, patch_type, folder_path, file_name, file_path, position
    """
    conditions = ["voice_name = ?"]
    params = [voice_name]
    if patch_type:
        conditions.append("patch_type = ?")
        params.append(patch_type)
    where = "WHERE " + " AND ".join(conditions)

    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT id, voice_name, patch_type, folder_path, file_name, file_path, position
            FROM voices {where}
            ORDER BY file_name ASC, position ASC
            """,
            params
        )
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


def get_voice_by_id(voice_id: int):
    """Returns the full row for a single voice record by primary key id, or None."""
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM voices WHERE id = ?", (voice_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_voice_occurrence_index(voice_id: int, file_path: str) -> int:
    """
    Returns the 0-based rank of voice_id among all rows sharing file_path, ordered
    by id ASC. This rank is stable and matches the order parser.parse_syx_file() /
    parser.extract_voice_blocks() return voices in for that same file, since rows
    for one file are inserted in that exact order at scan time and are never
    reordered afterward (folder deletion removes whole rows, it doesn't reshuffle
    survivors). Raises ValueError if voice_id isn't among file_path's rows.
    """
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM voices WHERE file_path = ? ORDER BY id ASC",
            (file_path,)
        )
        ids = [row[0] for row in cursor.fetchall()]
    return ids.index(voice_id)


# ---------------------------------------------------------------------------
# Cleanup: duplicate folder detection
# ---------------------------------------------------------------------------

def _compute_file_fingerprint(voice_rows):
    """
    Fingerprints a single .syx file from its voice rows (ordered by id ASC).
    Reconstructs banks by detecting when position resets to 1.
    """
    banks, current = [], []
    for row in voice_rows:
        if row['position'] == 1 and current:
            banks.append(current)
            current = []
        current.append((row['position'], row['voice_name']))
    if current:
        banks.append(current)
    normalized = [sorted(bank) for bank in banks]
    return hashlib.sha256(
        json.dumps(normalized, separators=(',', ':'), ensure_ascii=True).encode()
    ).hexdigest()


def _compute_folder_fingerprint(file_fp_map):
    """
    Fingerprints a folder from a {file_name -> file_hex} map.
    Sorting by filename ensures scan order doesn't affect the result.
    """
    return hashlib.sha256(
        json.dumps(sorted(file_fp_map.items()), separators=(',', ':'), ensure_ascii=True).encode()
    ).hexdigest()


def get_duplicate_folder_groups():
    """
    Identifies folders whose .syx file sets are content-identical.
    Two folders are duplicates when they contain exactly the same filenames
    with exactly the same voices at the same positions.

    Returns a list of groups, each with >= 2 folders:
    [
      {
        "fingerprint": "<sha256>",
        "folders": [
          { "folder_path": str, "file_count": int, "example_file_path": str },
          ...
        ]
      },
      ...
    ]
    Groups are sorted by folder count descending.
    """
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT folder_path, file_name, file_path, position, voice_name
            FROM voices
            ORDER BY folder_path ASC, file_path ASC, id ASC
        """)
        rows = [dict(r) for r in cursor.fetchall()]

    if not rows:
        return []

    # Build: folder_path -> file_path -> { file_name, rows[] }
    folders_data = {}
    for row in rows:
        fp = row['folder_path']
        fpath = row['file_path']
        folders_data.setdefault(fp, {})
        if fpath not in folders_data[fp]:
            folders_data[fp][fpath] = {'file_name': row['file_name'], 'rows': []}
        folders_data[fp][fpath]['rows'].append(
            {'position': row['position'], 'voice_name': row['voice_name']}
        )

    # Compute per-folder fingerprints
    folder_fp = {}
    folder_meta = {}
    for folder_path, files in folders_data.items():
        file_fp_map = {}
        example = None
        for file_path, fdata in files.items():
            if example is None:
                example = file_path
            file_fp_map[fdata['file_name']] = _compute_file_fingerprint(fdata['rows'])
        folder_fp[folder_path] = _compute_folder_fingerprint(file_fp_map)
        folder_meta[folder_path] = {'file_count': len(files), 'example_file_path': example}

    # Group folders by fingerprint, keep only groups with >= 2 folders
    groups = {}
    for folder_path, fp in folder_fp.items():
        groups.setdefault(fp, []).append(folder_path)

    result = []
    for fingerprint, paths in groups.items():
        if len(paths) < 2:
            continue
        result.append({
            'fingerprint': fingerprint,
            'folders': [
                {
                    'folder_path': p,
                    'file_count': folder_meta[p]['file_count'],
                    'example_file_path': folder_meta[p]['example_file_path'],
                }
                for p in sorted(paths)
            ]
        })
    result.sort(key=lambda g: len(g['folders']), reverse=True)
    return result


def delete_folder(folder_path: str):
    """
    Deletes the directory tree from disk first, then removes DB records on success.
    Performing disk deletion first ensures the DB is never left inconsistent when
    rmtree fails (e.g. permission error or file locked).

    Returns:
    {
        "deleted_path": str,
        "had_indexed_subfolders": bool,
        "error": str | None
    }
    """
    folder_norm = folder_path.replace('\\', '/')

    # Step 1: Delete from disk. Bail early on failure — DB is untouched.
    try:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
    except Exception as e:
        return {'deleted_path': folder_path, 'had_indexed_subfolders': False, 'error': str(e)}

    # Step 2: Disk deletion succeeded — now clean up DB records.
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(DISTINCT folder_path) FROM voices WHERE folder_path LIKE ?",
            (folder_norm + '/%',)
        )
        had_subfolders = cursor.fetchone()[0] > 0
        cursor.execute(
            "DELETE FROM voices WHERE folder_path = ? OR folder_path LIKE ?",
            (folder_norm, folder_norm + '/%')
        )
        conn.commit()

    return {'deleted_path': folder_path, 'had_indexed_subfolders': had_subfolders, 'error': None}
