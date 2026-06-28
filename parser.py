import logging

logger = logging.getLogger(__name__)

# DX7II/DX7S Performance record layout constants (verified against real .syx files).
# PMEM bulk dump: F0 43 0n 7E <size_msb> <size_lsb> <10-byte header> <records> F7
# Body begins with "LM  8973PM" (10 bytes), then 32 × 51-byte performance records.
# Performance name is 20 ASCII bytes starting at offset 31 within each record.
PMEM_FORMAT_BYTE  = 0x7E
PMEM_HEADER_SIZE  = 10    # "LM  8973PM" prefix before the records
PMEM_RECORD_SIZE  = 51    # bytes per performance record
PMEM_NAME_OFFSET  = 31    # offset of the 20-byte name within each record
PMEM_NAME_LENGTH  = 20    # performance name field width

# DX7II/DX7S Additional Voice (AMEM) record layout constants (verified against real .syx files).
# AMEM bulk dump: F0 43 0n 06 <size_msb> <size_lsb> <records> F7
# AMEM slots have no voice names; synthetic names are assigned.
AMEM_FORMAT_BYTE  = 0x06
AMEM_RECORD_SIZE  = 35    # bytes per extended-voice slot


def clean_voice_name(name_bytes: bytes) -> str:
    """Replaces non-printable ASCII bytes with spaces and strips the result."""
    cleaned = "".join(chr(b) if 32 <= b <= 126 else ' ' for b in name_bytes).strip()
    return cleaned if cleaned else "INIT VOICE"


def _parse_vmem_bank(data: bytes, bank_start: int, bank_index: int) -> list:
    """Extracts 32 voices from a VMEM bank starting at bank_start."""
    voices = []
    for v in range(32):
        offset = bank_start + v * 128
        voices.append({
            "name": clean_voice_name(data[offset + 118: offset + 128]),
            "position": v + 1,
            "bank_index": bank_index,
            "patch_type": "Voice",
        })
    return voices


def _merge_vmem_amem(results: list) -> list:
    """
    When a file contains both VMEM (Voice) and AMEM (Gen 2 Extended) banks, the DX7S/DX7II
    treats each matched pair as a single Gen 2 Voice. Merge by (bank_index, position):
    the AMEM slot keeps its 'Gen 2 Extended' type but takes the name from the paired VMEM voice.
    Unmatched VMEM voices stay as 'Voice'; unmatched AMEM slots keep their synthetic name.
    """
    vmem = [r for r in results if r['patch_type'] == 'Voice']
    amem = [r for r in results if r['patch_type'] == 'Gen 2 Extended']
    other = [r for r in results if r['patch_type'] not in ('Voice', 'Gen 2 Extended')]

    if not vmem or not amem:
        return results

    vmem_by_key = {(r['bank_index'], r['position']): r for r in vmem}
    consumed = set()
    merged = []

    for slot in amem:
        key = (slot['bank_index'], slot['position'])
        if key in vmem_by_key:
            consumed.add(key)
            merged.append({
                'name': vmem_by_key[key]['name'],
                'position': slot['position'],
                'bank_index': slot['bank_index'],
                'patch_type': 'Gen 2 Extended',
            })
        else:
            merged.append(slot)

    for voice in vmem:
        if (voice['bank_index'], voice['position']) not in consumed:
            merged.append(voice)

    return other + merged


def parse_syx_file(file_path: str) -> list:
    """
    Parses a .syx file and extracts all DX7/DX7II patches found within it.

    Detects the following Yamaha SysEx formats:
      - VMEM (format 0x09): DX7 32-voice bulk dump — patch_type "Voice"
      - PMEM (format 0x7E): DX7II/DX7S performance bulk dump — patch_type "Performance"
      - AMEM (format 0x06): DX7II/DX7S additional voice bulk dump — patch_type "Gen 2 Extended"
      - Raw 4096-byte fallback (no header) — patch_type "Voice"

    Returns a list of dicts:
    [
      {
        "name": str,
        "position": int,    # 1-indexed within the bank/block
        "bank_index": int,  # 0-indexed bank (for multi-bank files)
        "patch_type": str,  # "Voice" | "Performance" | "Gen 2 Extended"
      },
      ...
    ]
    """
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
    except (FileNotFoundError, PermissionError, OSError) as e:
        logger.error("Error reading file %s: %s", file_path, e)
        return []

    results = []
    data_len = len(data)
    vmem_bank_count = 0
    amem_bank_count = 0
    i = 0

    while i <= data_len - 6:
        # All Yamaha bulk-dump SysEx starts with: F0 43 <substatus/channel 0-7F>
        if not (data[i] == 0xF0 and data[i + 1] == 0x43 and data[i + 2] < 0x80):
            i += 1
            continue

        format_byte = data[i + 3]

        # ------------------------------------------------------------------ #
        # VMEM — 32-voice bulk dump: F0 43 0n 09 20 00 <4096 bytes> F7       #
        # ------------------------------------------------------------------ #
        if format_byte == 0x09 and data[i + 4] == 0x20 and data[i + 5] == 0x00:
            voice_data_start = i + 6
            if voice_data_start + 4096 <= data_len:
                results.extend(_parse_vmem_bank(data, voice_data_start, vmem_bank_count))
                vmem_bank_count += 1
                i = voice_data_start + 4096
            else:
                i += 1

        # ------------------------------------------------------------------ #
        # PMEM — DX7II/DX7S performance bulk dump: F0 43 0n 7E <msb> <lsb>  #
        # Body: 10-byte "LM  8973PM" header + 32 × 51-byte records.          #
        # 20-byte performance name starts at offset 31 within each record.    #
        # ------------------------------------------------------------------ #
        elif format_byte == PMEM_FORMAT_BYTE:
            size = (data[i + 4] << 7) | data[i + 5]
            data_start = i + 6
            records_start = data_start + PMEM_HEADER_SIZE
            if size > PMEM_HEADER_SIZE and data_start + size <= data_len:
                num_records = (size - PMEM_HEADER_SIZE) // PMEM_RECORD_SIZE
                for p in range(num_records):
                    offset = records_start + p * PMEM_RECORD_SIZE
                    name_end = offset + PMEM_NAME_OFFSET + PMEM_NAME_LENGTH
                    if name_end <= data_start + size:
                        name = clean_voice_name(data[offset + PMEM_NAME_OFFSET: name_end])
                        if name == "INIT VOICE":
                            name = "INIT PERF"
                    else:
                        name = "INIT PERF"
                    results.append({
                        "name": name,
                        "position": p + 1,
                        "bank_index": 0,
                        "patch_type": "Performance",
                    })
                i = data_start + size
            else:
                i += 1

        # ------------------------------------------------------------------ #
        # AMEM — DX7II/DX7S additional voice bulk dump: F0 43 0n 06 <msb>   #
        # 35-byte records, no names; synthetic slot names are assigned.       #
        # ------------------------------------------------------------------ #
        elif format_byte == AMEM_FORMAT_BYTE:
            size = (data[i + 4] << 7) | data[i + 5]
            data_start = i + 6
            if size > 0 and data_start + size <= data_len:
                num_slots = min(size // AMEM_RECORD_SIZE, 32)
                for s in range(num_slots):
                    results.append({
                        "name": f"Ext Voice {s + 1:02d}",
                        "position": s + 1,
                        "bank_index": amem_bank_count,
                        "patch_type": "Gen 2 Extended",
                    })
                amem_bank_count += 1
                i = data_start + size
            else:
                i += 1

        else:
            i += 1

    results = _merge_vmem_amem(results)

    # Raw 4096-byte fallback: headerless single-bank VMEM dump
    if not results and data_len == 4096:
        results = _parse_vmem_bank(data, 0, 0)

    return results
