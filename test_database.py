"""Tests for database.py.

Weighted towards the code paths that can destroy user data: delete_folder()
(the only shutil.rmtree on user files) and get_duplicate_folder_groups() (which
decides what the Cleanup tab offers to delete). Both were previously untested.

Every test runs against an isolated DX7_DATA_DIR -- see conftest.py.
"""

import os

import pytest

from conftest import make_rows


# --------------------------------------------------------------------------
# Grouping / search
# --------------------------------------------------------------------------

def test_groups_by_name_and_type_with_file_count(db, tmp_path):
    # Same patch name in two different files -> one row, file_count 2.
    db.insert_voices(make_rows(str(tmp_path / "a"), "one.syx", ["BASS", "LEAD"]))
    db.insert_voices(make_rows(str(tmp_path / "b"), "two.syx", ["BASS"]))
    res = db.get_all_voices()
    by_name = {v["voice_name"]: v for v in res["voices"]}
    assert res["total"] == 2
    assert by_name["BASS"]["file_count"] == 2
    assert by_name["LEAD"]["file_count"] == 1


def test_same_name_different_type_are_separate_groups(db, tmp_path):
    f = str(tmp_path / "a")
    db.insert_voices(make_rows(f, "v.syx", ["ORGAN"], patch_type="Voice"))
    db.insert_voices(make_rows(f, "p.syx", ["ORGAN"], patch_type="Performance"))
    assert db.get_all_voices()["total"] == 2


def test_result_limit_truncates_rows_but_not_total(db, tmp_path):
    names = [f"P{i:04d}" for i in range(db.RESULT_LIMIT + 25)]
    db.insert_voices(make_rows(str(tmp_path / "a"), "big.syx", names))
    res = db.get_all_voices()
    assert len(res["voices"]) == db.RESULT_LIMIT
    assert res["total"] == len(names)


def test_search_underscore_is_a_literal_not_a_wildcard(db, tmp_path):
    """`_` is a LIKE wildcard; unescaped, searching E_PIANO also matches EXPIANO."""
    db.insert_voices(make_rows(str(tmp_path / "a"), "x.syx", ["E_PIANO", "EXPIANO"]))
    found = [v["voice_name"] for v in db.get_all_voices(search_query="E_PIANO")["voices"]]
    assert found == ["E_PIANO"]


def test_search_percent_is_a_literal_not_a_wildcard(db, tmp_path):
    db.insert_voices(make_rows(str(tmp_path / "a"), "x.syx", ["100%", "ANYTHING"]))
    found = [v["voice_name"] for v in db.get_all_voices(search_query="%")["voices"]]
    assert found == ["100%"]


def test_folder_filter_includes_subfolders_but_not_lookalikes(db, tmp_path):
    """The underscore in Bank_1 must not match the X in BankX1."""
    db.insert_voices(make_rows(str(tmp_path / "Bank_1"), "a.syx", ["A"]))
    db.insert_voices(make_rows(str(tmp_path / "Bank_1" / "sub"), "b.syx", ["B"]))
    db.insert_voices(make_rows(str(tmp_path / "BankX1" / "sub"), "c.syx", ["C"]))
    found = {v["voice_name"]
             for v in db.get_all_voices(folder_filter=str(tmp_path / "Bank_1"))["voices"]}
    assert found == {"A", "B"}


def test_type_filter(db, tmp_path):
    f = str(tmp_path / "a")
    db.insert_voices(make_rows(f, "v.syx", ["A"], patch_type="Voice"))
    db.insert_voices(make_rows(f, "p.syx", ["B"], patch_type="Performance"))
    res = db.get_all_voices(type_filter="Performance")
    assert [v["voice_name"] for v in res["voices"]] == ["B"]


# --------------------------------------------------------------------------
# Occurrence index (drives the Voice Parameters page)
# --------------------------------------------------------------------------

def test_occurrence_index_matches_insertion_order(db, tmp_path):
    folder = str(tmp_path / "a")
    rows = make_rows(folder, "bank.syx", ["A", "B", "C"])
    db.insert_voices(rows)
    fp = rows[0]["file_path"]
    ids = [r["id"] for r in db.get_voices_by_name("B")]
    assert db.get_voice_occurrence_index(ids[0], fp) == 1


def test_occurrence_index_raises_for_unknown_id(db, tmp_path):
    rows = make_rows(str(tmp_path / "a"), "bank.syx", ["A"])
    db.insert_voices(rows)
    with pytest.raises(ValueError):
        db.get_voice_occurrence_index(999999, rows[0]["file_path"])


# --------------------------------------------------------------------------
# delete_folder -- the only rmtree on user data
# --------------------------------------------------------------------------

def _make_folder(base, name, files=("a.syx",)):
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    for f in files:
        (d / f).write_bytes(b"\xf0\x43\x00\x09")
    return d


def test_delete_refuses_a_folder_that_was_never_indexed(db, tmp_path):
    victim = _make_folder(tmp_path, "not_indexed")
    result = db.delete_folder(str(victim))
    assert result["error"] is not None
    assert "not an indexed folder" in result["error"].lower()
    assert victim.is_dir(), "refused delete must leave the directory alone"


def test_delete_removes_indexed_folder_and_its_rows(db, tmp_path):
    d = _make_folder(tmp_path, "indexed")
    db.insert_voices(make_rows(str(d), "a.syx", ["A"]))
    result = db.delete_folder(str(d))
    assert result["error"] is None
    assert not d.exists()
    assert db.count_voices() == 0


def test_delete_reports_indexed_subfolders(db, tmp_path):
    parent = _make_folder(tmp_path, "parent")
    child = _make_folder(tmp_path / "parent", "child")
    db.insert_voices(make_rows(str(parent), "a.syx", ["A"]))
    db.insert_voices(make_rows(str(child), "a.syx", ["B"]))
    result = db.delete_folder(str(parent))
    assert result["error"] is None
    assert result["had_indexed_subfolders"] is True
    assert db.count_voices() == 0


def test_delete_does_not_touch_lookalike_folder_rows(db, tmp_path):
    """Deleting Bank_1 must not delete BankX1 rows via the LIKE wildcard."""
    keep = _make_folder(tmp_path, "BankX1/sub")
    drop = _make_folder(tmp_path, "Bank_1")
    db.insert_voices(make_rows(str(drop), "a.syx", ["DROP"]))
    db.insert_voices(make_rows(str(keep), "b.syx", ["KEEP"]))
    db.delete_folder(str(drop))
    remaining = [v["voice_name"] for v in db.get_all_voices()["voices"]]
    assert remaining == ["KEEP"]
    assert keep.is_dir()


# --------------------------------------------------------------------------
# Duplicate detection -- what the Cleanup tab offers to delete
# --------------------------------------------------------------------------

def _folder_with(base, name, contents):
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    for fname, data in contents.items():
        (d / fname).write_bytes(data)
    return d


def _index(db, folder, names=("A",)):
    first = sorted(os.listdir(folder))[0]
    db.insert_voices(make_rows(str(folder), first, list(names)))


def test_byte_identical_folders_group(db, tmp_path):
    data = {"bank.syx": b"\x01" * 64}
    a = _folder_with(tmp_path, "A", data)
    b = _folder_with(tmp_path, "B", data)
    _index(db, a)
    _index(db, b)
    groups = db.get_duplicate_folder_groups()
    assert len(groups) == 1
    assert {os.path.basename(f["folder_path"]) for f in groups[0]["folders"]} == {"A", "B"}


def test_same_patch_names_but_different_bytes_do_not_group(db, tmp_path):
    """The old fingerprint used indexed names+positions, so an edited copy of a
    bank looked identical to the original and was offered up for deletion."""
    a = _folder_with(tmp_path, "A", {"bank.syx": b"\x01" * 64})
    b = _folder_with(tmp_path, "B", {"bank.syx": b"\x01" * 63 + b"\x02"})
    # Identical index entries for both -- only the bytes on disk differ.
    _index(db, a)
    _index(db, b)
    assert db.get_duplicate_folder_groups() == []


def test_extra_unparseable_file_prevents_a_match(db, tmp_path):
    """A file that yields no voices never reaches the index, so name-based
    fingerprinting could not see it."""
    a = _folder_with(tmp_path, "A", {"bank.syx": b"\x01" * 64})
    b = _folder_with(tmp_path, "B", {"bank.syx": b"\x01" * 64,
                                     "extra.syx": b"\xff" * 8})
    _index(db, a)
    _index(db, b)
    assert db.get_duplicate_folder_groups() == []


def test_single_folder_is_not_a_group(db, tmp_path):
    a = _folder_with(tmp_path, "A", {"bank.syx": b"\x01" * 64})
    _index(db, a)
    assert db.get_duplicate_folder_groups() == []


def test_folder_missing_from_disk_is_skipped(db, tmp_path):
    """Indexed but since deleted -- must not crash or be called a duplicate."""
    a = _folder_with(tmp_path, "A", {"bank.syx": b"\x01" * 64})
    _index(db, a)
    db.insert_voices(make_rows(str(tmp_path / "ghost"), "bank.syx", ["A"]))
    assert db.get_duplicate_folder_groups() == []


def test_is_indexed_file(db, tmp_path):
    rows = make_rows(str(tmp_path / "a"), "bank.syx", ["A"])
    db.insert_voices(rows)
    assert db.is_indexed_file(rows[0]["file_path"]) is True
    assert db.is_indexed_file(str(tmp_path / "a" / "other.syx")) is False
