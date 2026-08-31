"""Integration test: recursive directory scanning, end to end.

Run directly:  python verify_scanner.py

Uses a throwaway data directory, so it never touches the real voice index. That
matters because run_background_scan() calls database.clear_db() before indexing
-- pointed at the real database, this test would destroy a user's whole library.
DX7_DATA_DIR must be set before `import database`, which resolves DB_FILE at
import time.
"""

import os
import sqlite3
import shutil
import tempfile

_TMP_DATA_DIR = tempfile.mkdtemp(prefix="dx7_verify_")
os.environ["DX7_DATA_DIR"] = _TMP_DATA_DIR

import database  # noqa: E402  (must follow the DX7_DATA_DIR assignment)
from app import run_background_scan  # noqa: E402


def generate_mock_sysex_file(file_path, bank_name, num_voices=32):
    """Writes a mock 32-voice sysex dump to file_path."""
    data = bytearray()
    # Header: F0 43 00 09 20 00
    data.extend([0xF0, 0x43, 0x00, 0x09, 0x20, 0x00])

    for v in range(num_voices):
        voice_data = bytearray(128)
        # Create a name like "V01_BankA"
        name_str = f"V{v+1:02d}_{bank_name}".ljust(10)[:10]
        voice_data[118:128] = name_str.encode('ascii')
        data.extend(voice_data)

    data.append(0x00)  # dummy checksum
    data.append(0xF7)  # F7 end

    with open(file_path, "wb") as f:
        f.write(data)


def _all_rows():
    """Every indexed row, ungrouped.

    database.get_all_voices() deliberately returns one row per unique
    (voice_name, patch_type) and caps at RESULT_LIMIT, so it cannot answer
    "did every file get indexed at the right position?". Go to the table.
    """
    conn = sqlite3.connect(database.DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT voice_name, folder_path, file_name, file_path, position, "
            "patch_type FROM voices ORDER BY file_path, position"
        )]
    finally:
        conn.close()


def test_recursive_scanning():
    print("Initializing Integration Test for Recursive Scanner...")
    print(f"(isolated data dir: {_TMP_DATA_DIR})")
    database.init_db()

    # 1. Setup mock nested folder structure
    # test_root/
    #   bankA.syx
    #   level1/
    #     bankB.SYX
    #     level2/
    #       level3/
    #         bankC.syx
    #   empty_dir/
    test_root = "test_scan_root"
    level1 = os.path.join(test_root, "level1")
    level3 = os.path.join(level1, "level2", "level3")
    empty_dir = os.path.join(test_root, "empty_dir")

    os.makedirs(level3, exist_ok=True)
    os.makedirs(empty_dir, exist_ok=True)

    file_a = os.path.join(test_root, "bankA.syx")
    file_b = os.path.join(level1, "bankB.SYX")  # test case-insensitive extension
    file_c = os.path.join(level3, "bankC.syx")
    file_txt = os.path.join(test_root, "ignore_me.txt")  # should be ignored

    generate_mock_sysex_file(file_a, "BankA")
    generate_mock_sysex_file(file_b, "BankB")
    generate_mock_sysex_file(file_c, "BankC")

    with open(file_txt, "w") as f:
        f.write("This is not a sysex file.")

    try:
        # 2. Trigger the scan through the app's background runner function
        print(f"Scanning directory: {test_root}")
        run_background_scan(test_root)

        # 3. Retrieve results from database
        voices = _all_rows()

        # 4. Verify assertions
        # We expect 3 files * 32 voices = 96 voices total
        print(f"Total voices found in DB: {len(voices)}")
        assert len(voices) == 96, f"Expected 96 voices, got {len(voices)}"

        # Paths are stored with forward slashes (normalized by run_background_scan)
        def norm(p):
            return os.path.abspath(p).replace('\\', '/')

        # Verify BankA voices
        bank_a_voices = [v for v in voices if v["file_name"] == "bankA.syx"]
        assert len(bank_a_voices) == 32, "Expected 32 voices from bankA.syx"
        assert bank_a_voices[0]["voice_name"] == "V01_BankA"
        assert bank_a_voices[0]["position"] == 1
        assert bank_a_voices[0]["folder_path"] == norm(test_root)

        # Verify BankB voices (case insensitive extension test)
        bank_b_voices = [v for v in voices if v["file_name"] == "bankB.SYX"]
        assert len(bank_b_voices) == 32, "Expected 32 voices from bankB.SYX"
        assert bank_b_voices[10]["voice_name"] == "V11_BankB"
        assert bank_b_voices[10]["position"] == 11
        assert bank_b_voices[10]["folder_path"] == norm(level1)

        # Verify BankC voices (deeply nested subfolder test)
        bank_c_voices = [v for v in voices if v["file_name"] == "bankC.syx"]
        assert len(bank_c_voices) == 32, "Expected 32 voices from bankC.syx"
        assert bank_c_voices[31]["voice_name"] == "V32_BankC"
        assert bank_c_voices[31]["position"] == 32
        assert bank_c_voices[31]["folder_path"] == norm(level3)

        # The non-sysex file must not have been indexed
        assert not [v for v in voices if v["file_name"] == "ignore_me.txt"], \
            "ignore_me.txt should not have been indexed"

        # 5. Verify the grouped API contract the front-end actually consumes
        grouped = database.get_all_voices()
        assert set(grouped) == {"voices", "total"}, \
            f"get_all_voices() shape changed: {sorted(grouped)}"
        # 96 distinct names, all patch_type "Voice" -> 96 groups
        assert grouped["total"] == 96, f"Expected 96 groups, got {grouped['total']}"

        print("Recursive directory scanning tests PASSED successfully!")

    finally:
        # Cleanup mock folders
        if os.path.exists(test_root):
            shutil.rmtree(test_root)
            print("Cleaned up mock test files.")
        shutil.rmtree(_TMP_DATA_DIR, ignore_errors=True)


if __name__ == "__main__":
    test_recursive_scanning()
