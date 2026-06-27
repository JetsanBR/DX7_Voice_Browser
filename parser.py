import os
import re

def clean_voice_name(name_bytes: bytes) -> str:
    """
    Cleans up a 10-byte voice name from a DX7 Sysex file.
    Replaces non-printable ASCII characters with spaces,
    decodes to ASCII, and strips leading/trailing whitespace.
    """
    cleaned_chars = []
    for b in name_bytes:
        # DX7 uses standard 7-bit MIDI data bytes (0-127).
        # Printable ASCII range is 32 (space) to 126 (~).
        if 32 <= b <= 126:
            cleaned_chars.append(chr(b))
        else:
            cleaned_chars.append(' ')
    
    cleaned_name = "".join(cleaned_chars).strip()
    # Default name if empty or just spaces
    if not cleaned_name:
        cleaned_name = "INIT VOICE"
    return cleaned_name

def parse_syx_file(file_path: str) -> list:
    """
    Parses a .syx file to extract DX7/DX7II voices.
    Returns a list of dicts:
    [
      {
        "name": "VOICE NAME",
        "position": 1-32,
        "bank_index": 0,  # 0-indexed bank in case of multiple banks in one file
      },
      ...
    ]
    """
    if not os.path.exists(file_path):
        return []
    
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []

    voices = []
    data_len = len(data)
    
    # 1. Search for DX7 32-voice bulk dump headers
    # The header is 6 bytes: F0 43 <substatus/channel> 09 20 00
    # substatus/channel is a 7-bit data byte (0x00 to 0x7F).
    # We scan the file for this sequence.
    header_indices = []
    i = 0
    while i <= data_len - 6:
        if (data[i] == 0xF0 and 
            data[i+1] == 0x43 and 
            data[i+2] < 0x80 and 
            data[i+3] == 0x09 and 
            data[i+4] == 0x20 and 
            data[i+5] == 0x00):
            header_indices.append(i)
            # Skip past the expected length of a 32-voice bank (4104 bytes)
            # to avoid false positives inside the data block
            i += 4104
        else:
            i += 1

    # 2. Extract voices from each found bank
    if header_indices:
        for bank_idx, header_idx in enumerate(header_indices):
            voice_data_start = header_idx + 6
            # Ensure we have enough bytes for 32 voices (32 * 128 = 4096 bytes)
            if voice_data_start + 4096 <= data_len:
                for v in range(32):
                    start_offset = voice_data_start + v * 128
                    name_offset = start_offset + 118
                    name_bytes = data[name_offset:name_offset+10]
                    voice_name = clean_voice_name(name_bytes)
                    voices.append({
                        "name": voice_name,
                        "position": v + 1,
                        "bank_index": bank_idx
                    })
    # 3. Fallback: If no headers were found, check if it's a raw 4096-byte dump
    elif data_len == 4096:
        for v in range(32):
            start_offset = v * 128
            name_offset = start_offset + 118
            name_bytes = data[name_offset:name_offset+10]
            voice_name = clean_voice_name(name_bytes)
            voices.append({
                "name": voice_name,
                "position": v + 1,
                "bank_index": 0
            })
            
    return voices
