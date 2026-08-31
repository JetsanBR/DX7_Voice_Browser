"""Tests for app.py logic that can destroy data.

_seed_demo_data() is the one startup path that calls run_background_scan(), and
run_background_scan() begins with database.clear_db(). On the upgrade path an
existing install has a populated database but no sentinel file yet, so without
the count_voices() guard the first launch after an update wipes the user's
entire index. That is not hypothetical -- it happened during development.
"""

import importlib

import pytest

from conftest import make_rows


@pytest.fixture
def seeded_app(data_dir):
    """app + database, both bound to the isolated data dir."""
    import database
    import app
    importlib.reload(app)
    return app, database


def test_seeding_is_skipped_when_an_index_already_exists(seeded_app, tmp_path):
    app, database = seeded_app
    database.insert_voices(make_rows(str(tmp_path / "lib"), "mine.syx",
                                     ["MY PATCH", "ANOTHER"]))
    before = database.count_voices()

    app._seed_demo_data()

    assert database.count_voices() == before, "existing index must survive"
    names = {v["voice_name"] for v in database.get_all_voices()["voices"]}
    assert names == {"MY PATCH", "ANOTHER"}


def test_seeding_claims_the_sentinel_even_when_skipped(seeded_app, tmp_path, data_dir):
    """Otherwise it would re-check (and re-risk) on every single launch."""
    app, database = seeded_app
    database.insert_voices(make_rows(str(tmp_path / "lib"), "mine.syx", ["MY PATCH"]))
    app._seed_demo_data()
    assert (data_dir / app.DEMO_SENTINEL).exists()


def test_seeding_populates_an_empty_database(seeded_app, data_dir):
    app, database = seeded_app
    assert database.count_voices() == 0

    app._seed_demo_data()

    assert database.count_voices() > 0
    assert (data_dir / app.DEMO_SENTINEL).exists()
    # Demo patches must be copied OUT of the (ephemeral, under a onefile build)
    # resource dir, so the indexed paths still resolve on the next launch.
    demo = data_dir / "sample_patches"
    assert demo.is_dir()
    folders = database.get_all_folders()
    assert any(str(demo).replace("\\", "/") in f for f in folders)


def test_seeding_does_not_repeat_after_clear(seeded_app, data_dir):
    """Clear Database must not silently resurrect the demo patches."""
    app, database = seeded_app
    app._seed_demo_data()
    assert database.count_voices() > 0

    database.clear_db()
    app._seed_demo_data()

    assert database.count_voices() == 0


def test_seeding_failure_is_not_fatal(seeded_app, monkeypatch):
    """The app must still start if seeding blows up."""
    app, database = seeded_app

    def boom(*a, **k):
        raise OSError("disk on fire")

    monkeypatch.setattr(app.shutil, "copytree", boom)
    app._seed_demo_data()          # must not raise
