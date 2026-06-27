import sqlite3
import os

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
