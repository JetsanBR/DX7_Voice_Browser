import os
import tempfile
import parser

def generate_mock_sysex(headered=True, multi_bank=1):
    """
    Generates mock sysex data for testing.
    """
    data = bytearray()
    
    for b in range(multi_bank):
        if headered:
            # Header: F0 43 00 09 20 00
            data.extend([0xF0, 0x43, 0x00, 0x09, 0x20, 0x00])
        
        # 32 voices of 128 bytes each
        for v in range(32):
            voice_data = bytearray(128)
            # Create a 10-byte name for this voice
            # e.g., "BANKxV_01" -> 8 chars, pad to 10
            name_str = f"B{b}V_{v+1:02d}".ljust(10)[:10]
            name_bytes = name_str.encode('ascii')
            voice_data[118:128] = name_bytes
            data.extend(voice_data)
            
        if headered:
            # Checksum and F7
            data.append(0x00) # dummy checksum
            data.append(0xF7)
            
    return bytes(data)

def test_parse_syx_file():
    print("Running DX7 Sysex Parser tests...")
    
    # Test Case 1: Standard 32-voice headered sysex file
    mock_data_1 = generate_mock_sysex(headered=True)
    temp_file_1 = os.path.join(tempfile.gettempdir(), "test_bank_1.syx")
    with open(temp_file_1, "wb") as f:
        f.write(mock_data_1)
        
    try:
        voices = parser.parse_syx_file(temp_file_1)
        assert len(voices) == 32, f"Expected 32 voices, got {len(voices)}"
        for i, voice in enumerate(voices):
            expected_name = f"B0V_{i+1:02d}"
            assert voice["name"] == expected_name, f"Expected name {expected_name}, got {voice['name']}"
            assert voice["position"] == i + 1, f"Expected position {i+1}, got {voice['position']}"
            assert voice["bank_index"] == 0, "Expected bank index 0"
        print("Test Case 1 passed (Standard Headered SysEx)!")
    finally:
        if os.path.exists(temp_file_1):
            os.remove(temp_file_1)

    # Test Case 2: Raw 4096-byte headerless sysex file
    mock_data_2 = generate_mock_sysex(headered=False)
    temp_file_2 = os.path.join(tempfile.gettempdir(), "test_bank_2.syx")
    with open(temp_file_2, "wb") as f:
        f.write(mock_data_2)
        
    try:
        voices = parser.parse_syx_file(temp_file_2)
        assert len(voices) == 32, f"Expected 32 voices, got {len(voices)}"
        for i, voice in enumerate(voices):
            expected_name = f"B0V_{i+1:02d}"
            assert voice["name"] == expected_name, f"Expected name {expected_name}, got {voice['name']}"
            assert voice["position"] == i + 1, f"Expected position {i+1}, got {voice['position']}"
            assert voice["bank_index"] == 0, "Expected bank index 0"
        print("Test Case 2 passed (Raw Headerless SysEx)!")
    finally:
        if os.path.exists(temp_file_2):
            os.remove(temp_file_2)

    # Test Case 3: Concatenated multi-bank sysex file (2 banks)
    mock_data_3 = generate_mock_sysex(headered=True, multi_bank=2)
    temp_file_3 = os.path.join(tempfile.gettempdir(), "test_bank_3.syx")
    with open(temp_file_3, "wb") as f:
        f.write(mock_data_3)
        
    try:
        voices = parser.parse_syx_file(temp_file_3)
        assert len(voices) == 64, f"Expected 64 voices, got {len(voices)}"
        # Verify first bank
        for i in range(32):
            expected_name = f"B0V_{i+1:02d}"
            assert voices[i]["name"] == expected_name, f"Expected name {expected_name}, got {voices[i]['name']}"
            assert voices[i]["position"] == i + 1
            assert voices[i]["bank_index"] == 0
        # Verify second bank
        for i in range(32):
            expected_name = f"B1V_{i+1:02d}"
            assert voices[32+i]["name"] == expected_name, f"Expected name {expected_name}, got {voices[32+i]['name']}"
            assert voices[32+i]["position"] == i + 1
            assert voices[32+i]["bank_index"] == 1
        print("Test Case 3 passed (Concatenated Multi-Bank SysEx)!")
    finally:
        if os.path.exists(temp_file_3):
            os.remove(temp_file_3)

    # Test Case 4: Non-printable characters cleanup
    temp_file_4 = os.path.join(tempfile.gettempdir(), "test_bank_4.syx")
    # Create raw voice data with weird bytes in name
    raw_voice = bytearray(128)
    # Name bytes: 'A', 'B', 0x01 (non-printable), 'C', 0x7F (del), 'D', ' ', ' ', ' ', ' '
    raw_voice[118:128] = b'AB\x01C\x7fD    '
    
    # 32 copies of this voice to make exactly 4096 bytes
    with open(temp_file_4, "wb") as f:
        f.write(raw_voice * 32)
        
    try:
        voices = parser.parse_syx_file(temp_file_4)
        assert len(voices) == 32
        # Expected name: "AB C D" (non-printable bytes should be spaces, stripped at ends)
        assert voices[0]["name"] == "AB C D", f"Expected 'AB C D', got '{voices[0]['name']}'"
        print("Test Case 4 passed (Non-printable characters cleanup)!")
    finally:
        if os.path.exists(temp_file_4):
            os.remove(temp_file_4)
            
    print("All tests passed successfully!")

if __name__ == "__main__":
    test_parse_syx_file()
