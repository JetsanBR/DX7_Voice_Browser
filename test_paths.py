"""Tests for paths.py -- the module every filesystem location routes through.

These exist because verify_scanner.py and the pytest fixtures *depend* on the
DX7_DATA_DIR override working. If paths.py silently stopped reading it, those
tests would scan into the real database and clear_db() a user's whole library.
Nothing previously asserted the override took effect.
"""

import importlib
import os
import pathlib
import sys

import paths


def _reload():
    importlib.reload(paths)
    return paths


def test_data_dir_override(tmp_path, monkeypatch):
    monkeypatch.setenv("DX7_DATA_DIR", str(tmp_path / "custom"))
    p = _reload()
    assert p.user_data_dir() == tmp_path / "custom"
    assert p.db_path() == tmp_path / "custom" / "voices.db"


def test_data_dir_is_created_on_access(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "deeper"
    monkeypatch.setenv("DX7_DATA_DIR", str(target))
    p = _reload()
    assert p.user_data_dir().is_dir()


def test_falls_back_to_localappdata(tmp_path, monkeypatch):
    monkeypatch.delenv("DX7_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    p = _reload()
    assert p.user_data_dir() == tmp_path / "LocalAppData" / p.APP_NAME


def test_falls_back_to_appdata_when_localappdata_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("DX7_DATA_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    p = _reload()
    assert p.user_data_dir() == tmp_path / "Roaming" / p.APP_NAME


def test_derived_paths_sit_under_the_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DX7_DATA_DIR", str(tmp_path / "d"))
    p = _reload()
    base = p.user_data_dir()
    for derived in (p.db_path(), p.log_path(), p.demo_patches_dir(),
                    p.webview_storage_dir()):
        assert derived.parent == base


def test_resource_root_from_source_is_the_repo_not_the_cwd(tmp_path, monkeypatch):
    """The whole point of resource_root(): independent of where you launch."""
    monkeypatch.chdir(tmp_path)
    p = _reload()
    assert p.resource_root() == pathlib.Path(paths.__file__).resolve().parent
    assert (p.resource_path("static") / "index.html").is_file()


def test_frozen_resources_come_from_meipass(tmp_path, monkeypatch):
    """Under a onefile build, resources live in the ephemeral extract dir."""
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    p = _reload()
    assert p.is_frozen() is True
    assert p.resource_root() == tmp_path
    assert p.resource_path("static") == tmp_path / "static"


def test_not_frozen_when_running_from_source(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)
    p = _reload()
    assert p.is_frozen() is False
