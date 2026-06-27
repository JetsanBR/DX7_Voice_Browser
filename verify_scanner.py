import os
import shutil
import database
import parser
from app import run_background_scan

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
        
    data.append(0x00) # dummy checksum
    data.append(0xF7) # F7 end
    
    with open(file_path, "wb") as f:
        f.write(data)

def test_recursive_scanning():
    print("Initializing Integration Test for Recursive Scanner...")
    database.init_db()
    
    # 1. Setup mock nested folder structure
    # test_root/
    #   bankA.syx
    #   level1/
    #     bankB.syx
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
    file_b = os.path.join(level1, "bankB.SYX") # test case-insensitive extension
    file_c = os.path.join(level3, "bankC.syx")
    file_txt = os.path.join(test_root, "ignore_me.txt") # should be ignored
    
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
        voices = database.get_all_voices()
        
        # 4. Verify assertions
        # We expect 3 files * 32 voices = 96 voices total
        print(f"Total voices found in DB: {len(voices)}")
        assert len(voices) == 96, f"Expected 96 voices, got {len(voices)}"
        
        # Verify BankA voices
        bank_a_voices = [v for v in voices if v["file_name"] == "bankA.syx"]
        assert len(bank_a_voices) == 32, "Expected 32 voices from bankA.syx"
        assert bank_a_voices[0]["voice_name"] == "V01_BankA"
        assert bank_a_voices[0]["position"] == 1
        assert bank_a_voices[0]["folder_path"] == os.path.abspath(test_root)
        
        # Verify BankB voices (case insensitive extension test)
        bank_b_voices = [v for v in voices if v["file_name"] == "bankB.SYX"]
        assert len(bank_b_voices) == 32, "Expected 32 voices from bankB.SYX"
        assert bank_b_voices[10]["voice_name"] == "V11_BankB"
        assert bank_b_voices[10]["position"] == 11
        assert bank_b_voices[10]["folder_path"] == os.path.abspath(level1)
        
        # Verify BankC voices (deeply nested subfolder test)
        bank_c_voices = [v for v in voices if v["file_name"] == "bankC.syx"]
        assert len(bank_c_voices) == 32, "Expected 32 voices from bankC.syx"
        assert bank_c_voices[31]["voice_name"] == "V32_BankC"
        assert bank_c_voices[31]["position"] == 32
        assert bank_c_voices[31]["folder_path"] == os.path.abspath(level3)
        
        print("Recursive directory scanning tests PASSED successfully!")
        
    finally:
        # Cleanup mock folders
        if os.path.exists(test_root):
            shutil.rmtree(test_root)
            print("Cleaned up mock test files.")

if __name__ == "__main__":
    test_recursive_scanning()
