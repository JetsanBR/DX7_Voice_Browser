import sqlite3
import os
import hashlib
import json
import shutil

DB_FILE = "voices.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

RESULT_LIMIT = 200

def init_db():
    """Initializes the database schema and indexes if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS voices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voice_name TEXT NOT NULL,
            folder_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            position INTEGER NOT NULL
        )
    """)
    # Index for fast case-insensitive LIKE searches
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_voice_name ON voices (voice_name)
    """)
    conn.commit()
    conn.close()

def clear_db():
    """Clears all records from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM voices")
    conn.commit()
    conn.close()

def insert_voices(voices):
    """
    Inserts a list of voice records.
    voices is a list of dicts:
    [
      {
        "voice_name": str,
        "folder_path": str,
        "file_name": str,
        "file_path": str,
        "position": int
      },
      ...
    ]
    """
    if not voices:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO voices (voice_name, folder_path, file_name, file_path, position)
        VALUES (:voice_name, :folder_path, :file_name, :file_path, :position)
    """, voices)
    conn.commit()
    conn.close()

def get_all_voices(search_query=None):
    """
    Fetches up to RESULT_LIMIT voices grouped by unique voice_name, sorted
    alphabetically. Each row includes a `file_count` indicating how many
    distinct files share that name, plus representative patch data.
    Also returns the total count of unique names for the frontend counter.
    Returns: { "voices": [...], "total": <int> }
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if search_query:
        pattern = f"%{search_query}%"
        cursor.execute(
            "SELECT COUNT(DISTINCT voice_name) FROM voices WHERE voice_name LIKE ?",
            (pattern,)
        )
        total = cursor.fetchone()[0]
        cursor.execute("""
            SELECT
                voice_name,
                folder_path,
                file_name,
                file_path,
                position,
                COUNT(*) AS file_count
            FROM voices
            WHERE voice_name LIKE ?
            GROUP BY voice_name
            ORDER BY voice_name ASC
            LIMIT ?
        """, (pattern, RESULT_LIMIT))
    else:
        cursor.execute("SELECT COUNT(DISTINCT voice_name) FROM voices")
        total = cursor.fetchone()[0]
        cursor.execute("""
            SELECT
                voice_name,
                folder_path,
                file_name,
                file_path,
                position,
                COUNT(*) AS file_count
            FROM voices
            GROUP BY voice_name
            ORDER BY voice_name ASC
            LIMIT ?
        """, (RESULT_LIMIT,))

    rows = cursor.fetchall()
    conn.close()

    return {"voices": [dict(row) for row in rows], "total": total}


def get_voices_by_name(voice_name: str):
    """
    Returns all individual records that share the given voice_name.
    Used by the "duplicate files" modal to show every file containing
    a voice with that name.
    Returns: list of dicts with voice_name, folder_path, file_name, file_path, position
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT voice_name, folder_path, file_name, file_path, position
        FROM voices
        WHERE voice_name = ?
        ORDER BY file_name ASC, position ASC
    """, (voice_name,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT folder_path, file_name, file_path, position, voice_name
        FROM voices
        ORDER BY folder_path ASC, file_path ASC, id ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

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
    Removes all DB records for folder_path (and any indexed subfolders),
    then deletes the entire directory tree from disk via shutil.rmtree.

    Returns:
    {
        "deleted_path": str,
        "had_indexed_subfolders": bool,
        "error": str | None
    }
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if any indexed subfolder lives inside this directory
    cursor.execute(
        "SELECT COUNT(DISTINCT folder_path) FROM voices WHERE folder_path LIKE ?",
        (folder_path + os.sep + '%',)
    )
    had_subfolders = cursor.fetchone()[0] > 0

    # Remove DB records for this folder and any subfolders
    cursor.execute(
        "DELETE FROM voices WHERE folder_path = ? OR folder_path LIKE ?",
        (folder_path, folder_path + os.sep + '%')
    )
    conn.commit()
    conn.close()

    # Delete the directory tree from disk
    try:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        return {'deleted_path': folder_path, 'had_indexed_subfolders': had_subfolders, 'error': None}
    except Exception as e:
        return {'deleted_path': folder_path, 'had_indexed_subfolders': had_subfolders, 'error': str(e)}
