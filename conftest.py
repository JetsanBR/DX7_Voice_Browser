"""Shared pytest fixtures.

Every test that touches the database must run against a throwaway data
directory. `database.DB_FILE` is resolved at import time from
`paths.db_path()`, which reads DX7_DATA_DIR at call time -- so the env var has
to be set before `database` is first imported, and the module has to be
reloaded if a test wants a different location.

This matters more than usual here: run_background_scan() calls clear_db()
before indexing, so a test that leaks into the real data directory destroys the
user's entire voice library.
"""

import importlib
import os

import pytest


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """An isolated DX7_DATA_DIR, with `database` rebound to it."""
    d = tmp_path / "userdata"
    d.mkdir()
    monkeypatch.setenv("DX7_DATA_DIR", str(d))

    import paths
    importlib.reload(paths)
    import database
    importlib.reload(database)
    database.init_db()

    yield d

    # Leave the modules pointing at whatever the next test sets up.
    monkeypatch.delenv("DX7_DATA_DIR", raising=False)
    importlib.reload(paths)
    importlib.reload(database)


@pytest.fixture
def db(data_dir):
    """The freshly-reloaded database module, bound to an isolated file."""
    import database
    return database


def make_rows(folder, file_name, names, patch_type="Voice", start=1):
    """Builds voice rows the way run_background_scan does (forward slashes)."""
    folder = folder.replace(os.sep, "/")
    return [
        {
            "voice_name": n,
            "folder_path": folder,
            "file_name": file_name,
            "file_path": f"{folder}/{file_name}",
            "position": start + i,
            "patch_type": patch_type,
        }
        for i, n in enumerate(names)
    ]
