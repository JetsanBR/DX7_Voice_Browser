import sqlite3
import os
import hashlib
import json
import logging
import shutil
from contextlib import closing

import paths

logger = logging.getLogger("dx7.database")

# Absolute path, so the database is found no matter what the working directory
# is. _connect() reads this as a module global at call time and every query
# function goes through _connect(), so this one assignment reroutes them all.
DB_FILE = str(paths.db_path())
RESULT_LIMIT = 200


# Scans, deletes and reads can now overlap, and sqlite3's 5s default is short
# for a bulk scan holding a write transaction.
_CONNECT_TIMEOUT = 30.0


def _connect():
    """Opens a DB connection with Row factory enabled."""
    conn = sqlite3.connect(DB_FILE, timeout=_CONNECT_TIMEOUT)
    conn.row_factory = sqlite3.Row
    return conn


def _like_escape(value):
    r"""Escapes LIKE wildcards in a literal string.

    `%` and `_` are LIKE wildcards and both are legal in Windows paths — `_` is
    very common in patch-library folder names. Without this, deleting
    "C:/Patches/Bank_1" runs LIKE 'C:/Patches/Bank_1/%', whose `_` also matches
    "BankX1", silently deleting DB rows for files that still exist on disk.

    Callers must pair this with ESCAPE '\\' in the SQL.
    """
    return (value.replace('\\', '\\\\')
                 .replace('%', '\\%')
                 .replace('_', '\\_'))


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
        # These cover the predicates the app actually issues. Without them every
        # search keystroke costs two full scans of a table that reaches 300k+
        # rows. Created here so existing databases pick them up on next launch.
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_file_path ON voices (file_path)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_folder_path ON voices (folder_path)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_name_type ON voices (voice_name, patch_type)"
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


class BulkVoiceWriter:
    """Batched inserter for a scan.

    insert_voices() opens a connection, writes, commits and closes on every
    call. Doing that per .syx file means a 10,000-file library pays 10,000
    connections and 10,000 durable commits, which dominates scan time on a
    spinning disk. This holds one connection open and commits every
    `batch_size` files instead.

    Use as a context manager so the final partial batch is always flushed:

        with database.BulkVoiceWriter() as writer:
            for f in files:
                writer.add(rows_for(f))
    """

    _SQL = """
        INSERT INTO voices (voice_name, folder_path, file_name, file_path, position, patch_type)
        VALUES (:voice_name, :folder_path, :file_name, :file_path, :position, :patch_type)
    """

    def __init__(self, batch_size=200):
        self.batch_size = batch_size
        self._conn = None
        self._pending = 0

    def __enter__(self):
        self._conn = _connect()
        return self

    def add(self, voices):
        """Queues a file's worth of rows, committing when the batch is full."""
        if not voices:
            return
        self._conn.executemany(self._SQL, voices)
        self._pending += 1
        if self._pending >= self.batch_size:
            self._conn.commit()
            self._pending = 0

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                # A failed scan should not leave a half-written batch behind.
                self._conn.rollback()
        finally:
            self._conn.close()
            self._conn = None
        return False


def get_all_voices(search_query=None, folder_filter=None, type_filter=None):
    """
    Fetches up to RESULT_LIMIT patches grouped by (voice_name, patch_type), sorted
    alphabetically. Supports optional text search, folder prefix filter, and type filter.
    Returns: { "voices": [...], "total": <int> }
    """
    conditions, params = [], []
    if search_query:
        conditions.append("voice_name LIKE ? ESCAPE '\\'")
        params.append(f"%{_like_escape(search_query)}%")
    if folder_filter:
        # Normalize to forward slashes — paths in DB are stored with /
        folder_norm = folder_filter.replace('\\', '/')
        conditions.append("(folder_path = ? OR folder_path LIKE ? ESCAPE '\\')")
        params.extend([folder_norm, _like_escape(folder_norm) + '/%'])
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

def _hash_file_bytes(file_path, _chunk=1 << 16):
    """SHA-256 of a file's actual contents, or None if it can't be read."""
    h = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(_chunk)
                if not chunk:
                    break
                h.update(chunk)
    except OSError as e:
        logger.warning("Could not hash %s: %s", file_path, e)
        return None
    return h.hexdigest()


def _compute_folder_fingerprint(file_fp_map):
    """
    Fingerprints a folder from a {file_name -> content_hash} map.
    Sorting by filename ensures directory-listing order doesn't affect the
    result; lowercasing matches Windows' case-insensitive filesystem.
    """
    normalized = sorted((name.lower(), fp) for name, fp in file_fp_map.items())
    return hashlib.sha256(
        json.dumps(normalized, separators=(',', ':'), ensure_ascii=True).encode()
    ).hexdigest()


def is_indexed_file(file_path: str) -> bool:
    """Whether this exact file path is present in the index.

    Used to gate the Reveal-in-Explorer endpoint, which otherwise reports the
    existence of arbitrary paths and can launch unlimited Explorer windows.
    """
    normalized = file_path.replace(chr(92), '/')
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT 1 FROM voices WHERE file_path = ? LIMIT 1", (normalized,)
        ).fetchone()
    return row is not None


def get_duplicate_folder_groups():
    """
    Identifies folders whose .syx file sets are byte-for-byte identical.

    Folders are compared on the actual contents of their .syx files, read from
    disk. An earlier version fingerprinted the *indexed* patch names and
    positions instead, which was wrong in two ways that both ended with the
    user pressing an irreversible delete button:

      * Two banks with the same patch names but different synthesis parameters
        -- an edited copy of a factory ROM, the single most common case in a
        real library -- looked identical.
      * A file that parses to zero voices never reaches the voices table, so a
        folder containing an extra unparseable .syx looked identical to one
        without it.

    Enumerating from disk rather than from the index also means a folder whose
    contents changed since the last scan is compared as it is now.

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
        indexed_folders = [
            r['folder_path'] for r in conn.execute(
                "SELECT DISTINCT folder_path FROM voices ORDER BY folder_path ASC"
            )
        ]

    folder_fp = {}
    folder_meta = {}
    for folder_path in indexed_folders:
        if not os.path.isdir(folder_path):
            # Indexed but since moved or deleted; nothing to compare.
            continue
        try:
            names = sorted(
                e.name for e in os.scandir(folder_path)
                if e.is_file() and e.name.lower().endswith('.syx')
            )
        except OSError as e:
            logger.warning("Could not list %s: %s", folder_path, e)
            continue
        if not names:
            continue

        file_fp_map = {}
        unreadable = False
        for name in names:
            digest = _hash_file_bytes(os.path.join(folder_path, name))
            if digest is None:
                unreadable = True
                break
            file_fp_map[name] = digest
        if unreadable:
            # Never call a folder a duplicate on incomplete information.
            continue

        folder_fp[folder_path] = _compute_folder_fingerprint(file_fp_map)
        folder_meta[folder_path] = {
            'file_count': len(names),
            'example_file_path': os.path.join(folder_path, names[0]).replace(os.sep, '/'),
        }

    groups = {}
    for folder_path, fp in folder_fp.items():
        groups.setdefault(fp, []).append(folder_path)

    result = []
    for fingerprint, folder_paths in groups.items():
        if len(folder_paths) < 2:
            continue
        result.append({
            'fingerprint': fingerprint,
            'folders': [
                {
                    'folder_path': p,
                    'file_count': folder_meta[p]['file_count'],
                    'example_file_path': folder_meta[p]['example_file_path'],
                }
                for p in sorted(folder_paths)
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
    like_prefix = _like_escape(folder_norm) + '/%'

    # Step 0: refuse anything that is not a folder we actually indexed.
    #
    # Any local process can reach this endpoint, and the frontend only ever
    # sends paths that came back from /api/duplicates -- so requiring DB
    # membership costs no real functionality and removes what would otherwise
    # be an arbitrary-directory-deletion primitive.
    with closing(_connect()) as conn:
        known = conn.execute(
            "SELECT 1 FROM voices WHERE folder_path = ? LIMIT 1", (folder_norm,)
        ).fetchone()
    if known is None:
        logger.warning("Refused delete of non-indexed folder: %s", folder_path)
        return {
            'deleted_path': folder_path,
            'had_indexed_subfolders': False,
            'error': 'Refusing to delete: not an indexed folder.',
        }

    # Step 1: Delete from disk. Bail early on failure — DB is untouched.
    try:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
    except Exception as e:
        logger.exception("Failed to delete folder %s", folder_path)
        return {'deleted_path': folder_path, 'had_indexed_subfolders': False, 'error': str(e)}

    # Step 2: Disk deletion succeeded — now clean up DB records.
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(DISTINCT folder_path) FROM voices "
            "WHERE folder_path LIKE ? ESCAPE '\\'",
            (like_prefix,)
        )
        had_subfolders = cursor.fetchone()[0] > 0
        cursor.execute(
            "DELETE FROM voices WHERE folder_path = ? "
            "OR folder_path LIKE ? ESCAPE '\\'",
            (folder_norm, like_prefix)
        )
        conn.commit()

    return {'deleted_path': folder_path, 'had_indexed_subfolders': had_subfolders, 'error': None}
