# Engineering Specification: Yamaha DX7 / DX7s / DX7II 32-Voice SysEx Extraction

This document specifies how to parse, validate, and extract voice parameters from Yamaha DX7-family
System Exclusive (SysEx) bank dump files containing 32 voices.

---

## 1. SysEx File Stream Architecture

A standard 32-voice bank dump file (e.g. `DX7S INT 1-32.syx`) is a **concatenation of independent SysEx
messages**, back-to-back with no gaps. A robust parser should not assume fixed absolute offsets; instead
scan the byte stream for `$F0` ... `$F7` message boundaries and dispatch on the **Format Number** byte
(offset 3 of each message).

A typical factory dump file contains up to four messages:

| # | Approx. size | Header (hex) | Format | Content |
|---|---|---|---|---|
| 1 | 7 bytes | `F0 43 10 19 4D 00 F7` | Parameter Change | Utility/setup message (e.g. micro-tuning select) |
| 2 | 16,165 bytes | `F0 43 00 7E ...` | `$7E` | Universal bulk dump — system performances (out of scope for voice extraction; see §7.4) |
| 3 | 1,128 bytes | `F0 43 00 06 08 60 00 ...` | `$06` | 32 Additional (mk2/DX7s) Voice Parameters |
| 4 | 4,104 bytes | `F0 43 00 09 20 00 ...` | `$09` | 32 Core Voice Parameters |

**Important edge case:** an original **DX7 (mkI)** or **TX7** 32-voice dump will contain **only** the
format `$09` message — there is no format `$06` block, because the mkI has no additional-parameter
memory. The parser must treat the additional-voice block as **optional**. When absent, all extended
parameters should be reported using their documented power-on defaults (see §6), not left undefined.

To fully reconstruct voice `n` (0-indexed, 0–31), the parser must independently locate the `$09` message
and (if present) the `$06` message, then extract voice record `n` from each and merge the two structures.

---

## 2. Message Framing and Headers

### 2-1. Core 32-Voice Packed Bulk Dump (Format `$09`)

* **Total message size:** 4,104 bytes
* **Payload size:** 4,096 bytes (32 voices × 128 bytes)

| Byte Offset | Value (Hex) | Description |
| :--- | :--- | :--- |
| `00` | `$F0` | System Exclusive Status Start |
| `01` | `$43` | Yamaha Manufacturer ID |
| `02` | `$0n` | Substatus & Device Number (`n` = MIDI Channel `0`–`F`) |
| `03` | `$09` | Format Number: Packed 32 Core Voices |
| `04` | `$20` | Data Byte Count MSB (7-bit value; 4096 → `0100000`) |
| `05` | `$00` | Data Byte Count LSB (7-bit value; 4096 → `0000000`) |
| `06`–`4101` | `[Data]` | 4,096 bytes of continuous packed voice records (32 × 128 bytes) |
| `4102` | `[CS]` | 7-bit two's-complement checksum over the 4,096 data bytes |
| `4103` | `$F7` | End of Exclusive (EOX) |

### 2-2. 32-Additional Voice Packed Bulk Dump (Format `$06`)

* **Total message size:** 1,128 bytes
* **Payload size:** 1,120 bytes (32 voices × 35 bytes)

| Byte Offset | Value (Hex) | Description |
| :--- | :--- | :--- |
| `00` | `$F0` | System Exclusive Status Start |
| `01` | `$43` | Yamaha Manufacturer ID |
| `02` | `$0n` | Substatus & Device Number |
| `03` | `$06` | Format Number: Packed 32 Additional Voices |
| `04` | `$08` | Data Byte Count MSB (1120 → `0001000`) |
| `05` | `$60` | Data Byte Count LSB (1120 → `1100000`) |
| `06`–`1125` | `[Data]` | 1,120 bytes of continuous packed extended voice records (32 × 35 bytes) |
| `1126` | `[CS]` | 7-bit two's-complement checksum over the 1,120 data bytes |
| `1127` | `$F7` | End of Exclusive (EOX) |

---

## 3. File Validation / Corruption Detection

Before attempting to decode voice data, every file should be validated. A `.syx` file (or an individual
message inside it) should be flagged as **corrupted** if any of the following are true:

1. **No `0xF0` byte found** anywhere in the file — not a SysEx file at all.
2. **Truncated message** — an `0xF0` is found but no matching `0xF7` before EOF.
3. **Wrong manufacturer ID** — byte 1 of a message is not `0x43` (Yamaha).
4. **Byte-count mismatch** — for formats with a known, fixed payload size (`$00`, `$06`, `$09`), the
   declared byte count (bytes 4–5) doesn't match the expected value, or the actual message length
   doesn't match what the declared count implies.
5. **Bad EOX** — the byte immediately after the checksum byte is not `0xF7`.
6. **Checksum mismatch** — the computed 7-bit two's-complement checksum (§4) doesn't match the
   transmitted checksum byte. This is the most common signature of bit-rot / partial-transfer corruption
   in old `.syx` files, since a single flipped bit anywhere in the payload will change the sum.
7. **Stray/garbage bytes** between recognized messages, or trailing bytes after the last message — often
   caused by concatenating files incorrectly or partial overwrites.

Messages with a format number this tool doesn't decode (anything other than `$00`, `$06`, `$09`, `$7E`)
are **not** treated as corruption by themselves — they're simply left unparsed and reported as
informational notes, since a `.syx` file may legitimately contain message types outside this tool's
scope (e.g. micro-tuning dumps, fractional-scaling dumps).

### 3-1. Reference implementation

```python
import os

YAMAHA_ID = 0x43

# Formats that follow the "F0 43 0n FF ccH ccL [data...] [checksum] F7" bulk-dump
# structure, where the exact expected payload size is known and length + checksum
# can be fully verified.
CHECKSUM_FORMATS = {
    0x00: ("VCED - 1 Voice (unpacked)", 155),
    0x09: ("VMEM - 32 Voices (packed core)", 4096),
    0x06: ("AMEM - 32 Additional Voices (packed, DX7s/DX7II)", 1120),
}

# Formats that are real, expected messages but whose internal structure this
# tool doesn't model (e.g. the performance bulk dump). Only checked for basic
# frame integrity (F0 ... F7, correct manufacturer ID).
FRAMING_ONLY_FORMATS = {
    0x7E: "Universal Bulk Dump (performance block)",
}

def find_messages(data: bytes):
    """Yield (start, end) index pairs for each F0...F7 SysEx message found in data.
    end is the index of the F7 byte (inclusive), or None if truncated (no F7 found)."""
    i = 0
    n = len(data)
    while i < n:
        if data[i] == 0xF0:
            start = i
            j = i + 1
            while j < n and data[j] != 0xF7:
                j += 1
            if j < n:
                yield (start, j)
                i = j + 1
            else:
                yield (start, None)
                i = n
        else:
            i += 1

def compute_checksum(payload: bytes) -> int:
    return (128 - (sum(payload) & 0x7F)) & 0x7F

def validate_message(data: bytes, start: int, end):
    """Validate a single F0..F7 message. Returns a dict:
    {ok, format_name, errors, notes}
    'errors' cause the containing file to be reported as corrupted.
    'notes' are informational only (e.g. an unrecognized-but-well-formed message)."""
    result = {"start": start, "end": end, "ok": False, "format_name": None,
              "errors": [], "notes": []}

    if end is None:
        result["errors"].append("Truncated message: F0 found with no matching F7 before EOF")
        return result

    msg = data[start:end + 1]

    if len(msg) < 3 or msg[1] != YAMAHA_ID:
        result["errors"].append(
            f"Manufacturer ID byte is 0x{msg[1]:02X}" if len(msg) > 1 else "Message too short"
        )
        return result

    # Short parameter-change / utility messages (e.g. the 7-byte micro-tuning
    # select message) don't use the bulk-dump count+checksum structure - byte 3
    # there is part of a group/parameter address, not a format number.
    if len(msg) <= 8:
        result["format_name"] = "Parameter Change / Utility message"
        result["ok"] = True
        return result

    fmt = msg[3]

    if fmt in CHECKSUM_FORMATS:
        name, expected_count = CHECKSUM_FORMATS[fmt]
        result["format_name"] = name

        declared_count = (msg[4] << 7) | msg[5]
        if declared_count != expected_count:
            result["errors"].append(
                f"Declared byte count is {declared_count}, expected {expected_count} "
                f"for format 0x{fmt:02X}"
            )

        payload_start, payload_end = 6, 6 + declared_count
        expected_total_len = payload_end + 2  # + checksum byte + F7
        if len(msg) != expected_total_len:
            result["errors"].append(
                f"Message length is {len(msg)} bytes, expected {expected_total_len} "
                f"based on declared byte count {declared_count} "
                f"(file may be truncated, or the count field itself is corrupted)"
            )
            if len(msg) < expected_total_len:
                return result  # can't safely read payload/checksum

        payload = msg[payload_start:payload_end]
        transmitted_cs = msg[payload_end]
        eox = msg[payload_end + 1]

        if eox != 0xF7:
            result["errors"].append(f"Byte after checksum is 0x{eox:02X}, expected 0xF7 (EOX)")

        calc_cs = compute_checksum(payload)
        if calc_cs != transmitted_cs:
            result["errors"].append(
                f"Checksum mismatch: calculated 0x{calc_cs:02X}, file contains "
                f"0x{transmitted_cs:02X} - payload data is corrupted"
            )

    elif fmt in FRAMING_ONLY_FORMATS:
        result["format_name"] = FRAMING_ONLY_FORMATS[fmt]
        result["notes"].append("Structure not verified beyond frame boundaries by this tool")

    else:
        result["format_name"] = f"Unrecognized format 0x{fmt:02X}"
        result["notes"].append(
            f"Format 0x{fmt:02X} is not decoded by this tool - message is well-framed "
            f"but its contents were not checked"
        )

    result["ok"] = len(result["errors"]) == 0
    return result

def validate_file(path: str):
    """Validate an entire .syx file. Returns a report dict with 'valid' (bool),
    per-message results, and any file-level issues (stray bytes, no messages, etc.)."""
    report = {"path": path, "valid": False, "messages": [], "issues": []}

    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        report["issues"].append(f"Could not read file: {e}")
        return report

    if len(data) == 0:
        report["issues"].append("File is empty")
        return report

    cursor = 0
    found_any = False
    for start, end in find_messages(data):
        found_any = True
        if start > cursor:
            gap = data[cursor:start]
            report["issues"].append(
                f"{len(gap)} stray byte(s) before offset {start} not part of any "
                f"F0..F7 message (likely corruption or non-SysEx data mixed into the file)"
            )
        report["messages"].append(validate_message(data, start, end))
        cursor = (end + 1) if end is not None else len(data)

    if not found_any:
        report["issues"].append("No 0xF0 (SysEx start) byte found anywhere in the file")
        return report

    if cursor < len(data):
        report["issues"].append(f"{len(data) - cursor} trailing byte(s) after the last message end")

    all_msgs_ok = all(m["ok"] for m in report["messages"])
    report["valid"] = all_msgs_ok and len(report["issues"]) == 0
    return report

def scan_directory(dir_path: str, extension: str = ".syx"):
    """Scan a directory for .syx files and report which are valid vs corrupted."""
    results = []
    for fname in sorted(os.listdir(dir_path)):
        if not fname.lower().endswith(extension):
            continue
        results.append(validate_file(os.path.join(dir_path, fname)))
    return results

def print_report(results):
    valid_count = sum(1 for r in results if r["valid"])
    print(f"{valid_count}/{len(results)} files valid\n")
    for r in results:
        status = "VALID" if r["valid"] else "CORRUPTED"
        print(f"[{status}] {r['path']}")
        for issue in r["issues"]:
            print(f"    - {issue}")
        for m in r["messages"]:
            if m["errors"]:
                print(f"    - message at offset {m['start']} ({m['format_name']}):")
                for e in m["errors"]:
                    print(f"        ERROR: {e}")

if __name__ == "__main__":
    import sys
    results = scan_directory(sys.argv[1] if len(sys.argv) > 1 else ".")
    print_report(results)
```

### 3-2. Behavior to expect

* A genuinely intact factory dump reports `valid: True` with no messages flagged.
* A file with a single flipped/corrupted byte anywhere inside the `$09` or `$06` payload reports
  `valid: False`, with the specific message and a "Checksum mismatch" error pointing at it — this is
  the most useful signal for isolating **partial** corruption (e.g. one bad voice bank inside an
  otherwise-fine file, or a bad transfer that clipped mid-message).
* A file cut off mid-transfer reports a "Truncated message" error at the offset of the incomplete
  message.
* A file with extra bytes spliced between two valid messages (e.g. from a bad concatenation of multiple
  dumps) reports a "stray byte(s)" issue at the splice point, while the messages on either side can still
  validate individually.

When batch-scanning a folder of `.syx` files, use `scan_directory()` / `print_report()` to get a quick
valid/corrupted summary with the specific reason for each corrupted file, so files can be triaged (e.g.
partially-corrupted files where only the additional-voice block is bad can still have their core voices
recovered).

---

## 4. Checksum Verification Procedure

Applies identically to the `$09`, `$06`, and `$00` payloads. Skip the framing bytes (`F0…count LSB`
header and the trailing `[CS] F7`); sum only the data payload bytes.

$$\text{Checksum} = (128 - (\sum \text{Data Bytes} \bmod 128)) \bmod 128$$

This is the same `compute_checksum()` function used by the validator in §3-1.

---

## 5. Core Voice Parameter Memory Mapping — Format `$09` (128 Bytes/Voice, PACKED)

Each voice occupies a contiguous 128-byte block within the 4,096-byte payload:
`voice_bytes = payload[voice_index * 128 : voice_index * 128 + 128]`.

The first **102 bytes** (offsets `0`–`101`) hold six operators × **17 bytes each**. Operators are stored
**OP6 first, down to OP1 last** (i.e. block index 0 = OP6, block index 5 = OP1).

### 5-1. Operator Structure (17 bytes per operator, repeated ×6)

| Offset (per OP) | Bits used | Range | Parameter |
| :---: | :---: | :---: | :--- |
| `0` | 7 | 0–99 | EG Rate 1 |
| `1` | 7 | 0–99 | EG Rate 2 |
| `2` | 7 | 0–99 | EG Rate 3 |
| `3` | 7 | 0–99 | EG Rate 4 |
| `4` | 7 | 0–99 | EG Level 1 |
| `5` | 7 | 0–99 | EG Level 2 |
| `6` | 7 | 0–99 | EG Level 3 |
| `7` | 7 | 0–99 | EG Level 4 |
| `8` | 7 | 0–99 | Keyboard Level Scaling Break Point |
| `9` | 7 | 0–99 | Keyboard Level Scaling Left Depth |
| `10` | 7 | 0–99 | Keyboard Level Scaling Right Depth |
| `11` | bits 0–1 | 0–3 | Keyboard Level Scaling **Left** Curve (`-LIN`,`-EXP`,`+LIN`,`+EXP`) |
| `11` | bits 2–3 | 0–3 | Keyboard Level Scaling **Right** Curve |
| `12` | bits 0–2 | 0–7 | Keyboard Rate Scaling |
| `12` | bits 3–6 | 0–14 | Oscillator Detune (7 = center/no detune) |
| `13` | bits 0–1 | 0–3 | Operator Amplitude Modulation Sensitivity |
| `13` | bits 2–4 | 0–7 | Keyboard Touch/Velocity Sensitivity |
| `14` | 7 | 0–99 | Operator Total Output Level |
| `15` | bit 0 | 0–1 | Oscillator Frequency Mode (0 = Ratio, 1 = Fixed) |
| `15` | bits 1–5 | 0–31 | Oscillator Frequency Coarse |
| `16` | 7 | 0–99 | Oscillator Frequency Fine |

Decode helpers:

```
left_curve   = byte11 & 0x03
right_curve  = (byte11 >> 2) & 0x03
rate_scaling = byte12 & 0x07
detune       = (byte12 >> 3) & 0x0F
amp_mod_sens = byte13 & 0x03
vel_sens     = (byte13 >> 2) & 0x07
osc_mode     = byte15 & 0x01
freq_coarse  = (byte15 >> 1) & 0x1F
```

### 5-2. Global Voice Parameters (offsets 102–127, 26 bytes total)

| Offset | Bits used | Range | Parameter |
| :---: | :---: | :---: | :--- |
| `102` | 7 | 0–99 | Pitch EG Rate 1 |
| `103` | 7 | 0–99 | Pitch EG Rate 2 |
| `104` | 7 | 0–99 | Pitch EG Rate 3 |
| `105` | 7 | 0–99 | Pitch EG Rate 4 |
| `106` | 7 | 0–99 | Pitch EG Level 1 |
| `107` | 7 | 0–99 | Pitch EG Level 2 |
| `108` | 7 | 0–99 | Pitch EG Level 3 |
| `109` | 7 | 0–99 | Pitch EG Level 4 |
| `110` | 5 | 0–31 | Algorithm Selector (add 1 for the display value 1–32) |
| `111` | bits 0–2 | 0–7 | Feedback Level |
| `111` | bit 3 | 0–1 | Oscillator Key Sync (0 = Off, 1 = On) |
| `112` | 7 | 0–99 | LFO Speed |
| `113` | 7 | 0–99 | LFO Delay Time |
| `114` | 7 | 0–99 | LFO Pitch Modulation Depth (PMD) |
| `115` | 7 | 0–99 | LFO Amplitude Modulation Depth (AMD) |
| `116` | bit 0 | 0–1 | LFO Key Sync (0 = Off, 1 = On) |
| `116` | bits 1–3 | 0–5 | LFO Waveform (`TRI`,`SAW DOWN`,`SAW UP`,`SQUARE`,`SINE`,`S/HOLD`) |
| `116` | bits 4–6 | 0–7 | LFO Pitch Modulation Sensitivity |
| `117` | 6 | 0–48 | Keyboard Transpose (24 = center, C3 baseline) |
| `118`–`127` | ASCII | — | Voice Name (10 characters, left-padded with spaces) |

Decode helpers:

```
feedback   = byte111 & 0x07
osc_sync   = (byte111 >> 3) & 0x01
lfo_sync   = byte116 & 0x01
lfo_wave   = (byte116 >> 1) & 0x07
lfo_pms    = (byte116 >> 4) & 0x07
name       = bytes[118:128]  # ASCII; DX7 uses a few nonstandard codes (see §7.3)
```

> **Scope note:** the DX7 mkI packed 32-voice bulk format (`$09`) does not include Operator Enable
> Status/"screen active operator" bits, pitch-bend range/step, portamento, or controller (mod wheel /
> foot / breath / aftertouch) assignments. On DX7s/DX7II this data lives in the separate format `$06`
> block described in §6.

---

## 6. Additional (mk2/DX7s) Voice Parameter Mapping — Format `$06` (35 Bytes/Voice, PACKED)

Each voice occupies: `voice_bytes = payload[voice_index * 35 : voice_index * 35 + 35]`.

| Offset | Bits used | Range (default) | Parameter |
| :---: | :---: | :---: | :--- |
| `0` | bits 0–5 | 0–1 each | Operator Scaling Mode, one bit per operator: bit0=OP1 … bit5=OP6 (0 = Normal, 1 = Fractional) |
| `1` | bits 0–2 / 3–5 | 0–7 each | Operator AM Sensitivity: OP6 (bits 3–5), OP5 (bits 0–2) |
| `2` | bits 0–2 / 3–5 | 0–7 each | Operator AM Sensitivity: OP4 (bits 3–5), OP3 (bits 0–2) |
| `3` | bits 0–2 / 3–5 | 0–7 each | Operator AM Sensitivity: OP2 (bits 3–5), OP1 (bits 0–2) |
| `4` | bits 0–1 | 0–3 (0) | Pitch EG Range (`0`=8oct, `1`=4oct, `2`=1oct, `3`=1/2oct) |
| `4` | bit 2 | 0–1 (0) | LFO Key Trigger (0 = Single, 1 = Multi) |
| `4` | bit 3 | 0–1 (0) | Pitch EG by Velocity Switch (0 = Off, 1 = On) |
| `4` | bits 4–6 | 0–7 (0) | Random Pitch Depth |
| `5` | bit 0 | 0–1 (0) | Key Assign: Poly (0) / Mono (1) |
| `5` | bit 1 | 0–1 (0) | Unison: Off (0) / On (1) |
| `5` | bits 2–6 | 0–12 (2) | Pitch Bend Range |
| `6` | bits 0–3 | 0–12 (0) | Pitch Bend Step |
| `6` | bits 4–5 | 0–3 (0) | Pitch Bend Mode (`0`=Normal,`1`=Low,`2`=High,`3`=Key-On) |
| `7` | bit 0 | 0–1 (0) | Portamento Mode (0 = Retain/Follow, 1 = Fingered/Fulltime) |
| `7` | bits 1–4 | 0–12 (0) | Portamento Step |
| `8` | 7 | 0–99 (0) | Portamento Time |
| `9` | 7 | 0–99 (0) | Mod Wheel → Pitch Modulation Depth |
| `10` | 7 | 0–99 (0) | Mod Wheel → Amplitude Modulation Depth |
| `11` | 7 | 0–99 (0) | Mod Wheel → EG Bias |
| `12` | 7 | 0–99 (0) | Foot Controller 1 → Pitch Mod |
| `13` | 7 | 0–99 (0) | Foot Controller 1 → Amp Mod |
| `14` | 7 | 0–99 (0) | Foot Controller 1 → EG Bias |
| `15` | 7 | 0–99 (0) | Foot Controller 1 → Volume |
| `16` | 7 | 0–99 (0) | Breath Controller → Pitch Mod |
| `17` | 7 | 0–99 (0) | Breath Controller → Amp Mod |
| `18` | 7 | 0–99 (0) | Breath Controller → EG Bias |
| `19` | 7 | 0–100 (50) | Breath Controller → Pitch Bias (stored value − 50 = signed range) |
| `20` | 7 | 0–99 (0) | Aftertouch → Pitch Mod |
| `21` | 7 | 0–99 (0) | Aftertouch → Amp Mod |
| `22` | 7 | 0–99 (0) | Aftertouch → EG Bias |
| `23` | 7 | 0–100 (50) | Aftertouch → Pitch Bias (stored value − 50 = signed range) |
| `24` | bits 0–2 | 0–7 (0) | Pitch EG Rate Scaling |
| `25` | — | — | Reserved |
| `26` | 7 | 0–99 (0) | Foot Controller 2 → Pitch Mod |
| `27` | 7 | 0–99 (0) | Foot Controller 2 → Amp Mod |
| `28` | 7 | 0–99 (0) | Foot Controller 2 → EG Bias |
| `29` | 7 | 0–99 (99) | Foot Controller 2 → Volume |
| `30` | 7 | 0–99 (0) | MIDI-in Controller → Pitch Mod |
| `31` | 7 | 0–99 (0) | MIDI-in Controller → Amp Mod |
| `32` | 7 | 0–99 (0) | MIDI-in Controller → EG Bias |
| `33` | 7 | 0–99 (0) | MIDI-in Controller → Volume |
| `34` | bits 0–2 | 0–7 (0) | Unison Detune Depth |
| `34` | bit 3 | 0–1 (0) | Foot Controller 1 as CS1 switch |

Decode helpers:

```
osc_scaling(op)  = (byte0 >> op) & 0x01                      # op = 0..5 → OP1..OP6
osc_amp_mod(op)  = (byte[1+op//2] >> (0 if op%2 else 3)) & 0x07   # pairs: (OP6,OP5) (OP4,OP3) (OP2,OP1)
peg_range        = byte4 & 0x03
lfo_key_trigger  = (byte4 >> 2) & 0x01
peg_vel_sw       = (byte4 >> 3) & 0x01
random_pitch     = (byte4 >> 4) & 0x07
key_mode_mono    = byte5 & 0x01
unison_on        = (byte5 >> 1) & 0x01
pitch_bend_range = (byte5 >> 2) & 0x1F
pitch_bend_step  = byte6 & 0x0F
pitch_bend_mode  = (byte6 >> 4) & 0x03
portamento_mode  = byte7 & 0x01
portamento_step  = (byte7 >> 1) & 0x1F
pitch_bias_signed = byte19 - 50   # applies to bytes 19 and 23
unison_detune    = byte34 & 0x07
fc1_as_cs1       = (byte34 >> 3) & 0x01
```

**If the format `$06` block is absent from the input file** (plain DX7 mkI dumps), populate every field
in this section with its documented default (shown in parentheses above) rather than leaving it
undefined, so downstream tooling always receives a complete voice model.

---

## 7. Guidance for Implementation (Claude Code)

### 7-1. Parsing algorithm (recommended)

1. Read the file as raw bytes.
2. Run the file-level validation in §3 first. Surface a clear pass/fail + reason list before attempting
   to decode voices.
3. Scan for all `F0 … F7` message boundaries.
4. For each message, read byte 3 (Format Number) and byte 1 (must be `0x43`/Yamaha) to classify it.
   Ignore/pass through any format the tool doesn't need (e.g. `$7E` performance block, utility messages).
5. For a `$09` message: verify checksum, then slice the 4,096-byte payload into 32 × 128-byte voice
   records and decode each with §5.
6. For a `$06` message (optional): verify checksum, slice the 1,120-byte payload into 32 × 35-byte
   records, decode each with §6.
7. Merge core + additional records by index (0–31) into one voice model per voice. If no `$06` message
   was found, fill additional fields with documented defaults.
8. Emit one structured record per voice (e.g. JSON) — see suggested schema below.

### 7-2. Suggested output schema (per voice)

```json
{
  "index": 0,
  "name": "MellowHorn",
  "algorithm": 2,
  "feedback": 7,
  "oscillator_key_sync": true,
  "transpose": 12,
  "operators": [ { "op": 6, "eg_rate": [..], "eg_level": [..], "...": "..." }, "... x6" ],
  "pitch_eg": { "rate": [..], "level": [..] },
  "lfo": { "speed": 30, "delay": 0, "pmd": 0, "amd": 0, "sync": true, "waveform": "TRIANGLE", "pitch_mod_sensitivity": 2 },
  "additional": { "present": true, "unison": false, "key_mode": "poly", "pitch_bend_range": 2, "...": "..." }
}
```

### 7-3. Voice name character handling

Names are raw 7-bit ASCII but the DX7 character set uses a couple of non-standard codes historically
mapped as: byte `0x5C` (`\`) is displayed as `¥` (Yen) on Japanese-market units, and bytes `0x7E`/`0x7F`
render as `«`/`»` on the LCD. Anything below `0x20` (space) should be treated as invalid/blank. Trim
trailing spaces when displaying, but preserve them if round-tripping to a re-exportable `.syx`.

### 7-4. Explicitly out of scope (flag, don't attempt to fully parse unless requested)

- The Performance bulk block (format `$7E`, 16,165 bytes) — system performance/layer data, not voice data.
* Microtuning and Fractional Scaling bulk dumps (separate, much larger SysEx formats on DX7II/DX7s, not
  present in a standard 32-voice factory dump).
* Single-voice edit-buffer dumps (format `$00`, unpacked 155/163-byte layout) — a different structure
  from the packed bulk format described here; only add support for this if the tool needs to read
  single-voice `.syx` files in addition to 32-voice banks.

### 7-5. Suggested tech stack

Given the byte-level bit-packing throughout, a typed, struct/bitfield-friendly language keeps this
tractable — e.g. Python with the `struct`/manual bit-mask approach shown above (fastest to prototype and
test), or TypeScript/Node with a small typed `DataView`-based reader if the target is a web app. Keep the
core/additional decoders, and the validator, as pure functions (`bytes -> dict`) so they're independently
unit-testable against the fixture in §8.

---

## 8. Test Fixture Reference (`DX7S INT 1-32.syx`)

Use this as ground truth for unit tests.

* File size: 21,404 bytes. 4 messages, contiguous, no padding.
* Message table: see §1.
* `$06` payload checksum: `0x6E` (110). `$09` payload checksum: `0x1E` (30).
* Decoded voice names (offset 118–127 of each 128-byte core record), in order:

| # | Name | # | Name | # | Name | # | Name |
|---|---|---|---|---|---|---|---|
| 1 | MellowHorn | 9 | BC Trumpet | 17 | EleCello A | 25 | SpitFlute |
| 2 | SilvaBrass | 10 | FrenchHorn | 18 | EleCello B | 26 | PanFloot |
| 3 | ReverbBras | 11 | Strings | 19 | Violins | 27 | Piccolo |
| 4 | Tuba | 12 | HallOrch | 20 | Bassoon | 28 | Sax |
| 5 | Trombone | 13 | NewOrchest | 21 | Clarinet | 29 | Harmonica |
| 6 | HardTrumps | 14 | Analog-Str | 22 | Oboe | 30 | Harp |
| 7 | Trumpet A | 15 | LiveStrg | 23 | Flute | 31 | EbonyIvory |
| 8 | SilvaTrmpt | 16 | BowedBass | 24 | SongFlute | 32 | PianoBrite |

* Voice 1 ("MellowHorn") decoded core parameters: algorithm 2 (stored `1`), feedback 7, oscillator key
  sync on, LFO speed 30, LFO waveform `TRI` (0), LFO pitch mod sensitivity 2, transpose 12.
* Voice 1 additional-block check: byte 19 = `0x32` (50, neutral breath pitch-bias), byte 23 = `0x32`
  (50, neutral aftertouch pitch-bias), byte 29 = `0x63` (99, full foot-controller-2 volume).

Recommend committing this file (or a trimmed 1–2 voice extract) into the test suite as a fixture, along
with a few deliberately-corrupted copies (flipped byte in the payload, truncated mid-message, garbage
bytes spliced between messages) to exercise the validator in §3.
