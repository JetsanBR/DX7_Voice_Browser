import os
import tempfile

import parser
import voice_params


def _make_op_bytes(eg_rate, eg_level, break_point, left_depth, right_depth,
                    left_curve, right_curve, rate_scaling, detune_raw,
                    amp_mod_sens, vel_sens, level, osc_mode, freq_coarse, freq_fine):
    """Builds one 17-byte packed operator block (spec §5-1)."""
    b = bytearray(17)
    b[0:4] = eg_rate
    b[4:8] = eg_level
    b[8] = break_point
    b[9] = left_depth
    b[10] = right_depth
    b[11] = (left_curve & 0x03) | ((right_curve & 0x03) << 2)
    b[12] = (rate_scaling & 0x07) | ((detune_raw & 0x0F) << 3)
    b[13] = (amp_mod_sens & 0x03) | ((vel_sens & 0x07) << 2)
    b[14] = level
    b[15] = (osc_mode & 0x01) | ((freq_coarse & 0x1F) << 1)
    b[16] = freq_fine
    return bytes(b)


def _make_core_voice_bytes():
    """
    Builds a synthetic 128-byte core voice block modeled on the spec §8 test
    fixture (MellowHorn: algorithm 2, feedback 7, osc key sync on, LFO speed 30,
    LFO waveform TRI, LFO key sync off, LFO pitch mod sensitivity 2, transpose 12),
    with a distinctive, individually-checkable OP1 block to verify the OP6->OP1
    storage-order reversal and every bitfield in the operator layout.
    """
    core = bytearray(128)

    op1_bytes = _make_op_bytes(
        eg_rate=[1, 2, 3, 4], eg_level=[5, 6, 7, 8], break_point=9,
        left_depth=10, right_depth=11, left_curve=1, right_curve=2,
        rate_scaling=3, detune_raw=10, amp_mod_sens=2, vel_sens=5,
        level=88, osc_mode=1, freq_coarse=7, freq_fine=33,
    )
    # OP1 is logical operator 1 -> stored last (storage slot 5, bytes 85:102).
    core[85:102] = op1_bytes
    # Other operators (storage slots 0-4, OP6..OP2) are left as all-zero — decoded
    # but not asserted on in this test.

    core[102:106] = [99, 95, 95, 99]   # pitch EG rates
    core[106:110] = [50, 48, 50, 50]   # pitch EG levels
    core[110] = 1                       # algorithm raw (display = raw + 1 = 2)
    core[111] = 7 | (1 << 3)             # feedback=7, osc key sync on
    core[112] = 30                      # LFO speed
    core[113] = 0                       # LFO delay
    core[114] = 0                       # LFO PMD
    core[115] = 0                       # LFO AMD
    core[116] = 0 | (0 << 1) | (2 << 4)  # LFO sync off, wave TRI(0), PMS 2
    core[117] = 12                       # transpose (C2)
    core[118:128] = b"MellowHorn"

    return bytes(core)


def _make_additional_voice_bytes():
    """
    Builds a synthetic 35-byte AMEM block covering the three spec §8 checkpoints
    (BC pitch bias neutral, AT pitch bias neutral, FC2 volume full) plus a
    non-default pitch bend range / key mode to confirm those bitfields decode too.
    """
    b = bytearray(35)
    b[5] = 1 | (5 << 2)   # key mode mono=1 (Monophonic), pitch bend range=5
    b[19] = 50            # BC pitch bias -> neutral (50 - 50 = 0)
    b[23] = 50            # AT pitch bias -> neutral (50 - 50 = 0)
    b[29] = 99            # FC2 volume
    return bytes(b)


def test_decode_core_voice():
    core = voice_params.decode_core_voice(_make_core_voice_bytes())

    assert core["name"] == "MellowHorn", core["name"]
    assert core["algorithm"] == 2, core["algorithm"]
    assert core["feedback"] == 7, core["feedback"]
    assert core["osc_key_sync"] is True
    assert core["transpose"] == 12, core["transpose"]
    assert core["transpose_name"] == "C2", core["transpose_name"]
    assert core["lfo"]["speed"] == 30
    assert core["lfo"]["wave_name"] == "TRI"
    assert core["lfo"]["sync"] is False
    assert core["lfo"]["pitch_mod_sensitivity"] == 2
    assert core["pitch_eg"]["rate"] == [99, 95, 95, 99]
    assert core["pitch_eg"]["level"] == [50, 48, 50, 50]

    assert len(core["operators"]) == 6
    op1 = core["operators"][0]
    assert op1["op"] == 1, "First entry must be logical OP1 (storage-order reversal)"
    assert op1["eg_rate"] == [1, 2, 3, 4]
    assert op1["eg_level"] == [5, 6, 7, 8]
    assert op1["break_point"] == 9
    assert op1["left_depth"] == 10
    assert op1["right_depth"] == 11
    assert op1["left_curve"] == 1
    assert op1["right_curve"] == 2
    assert op1["rate_scaling"] == 3
    assert op1["detune"] == 3, "detune display = raw(10) - 7"
    assert op1["amp_mod_sens"] == 2
    assert op1["vel_sens"] == 5
    assert op1["level"] == 88
    assert op1["osc_mode"] == "Fixed"
    assert op1["freq_coarse"] == 7
    assert op1["freq_fine"] == 33
    assert core["operators"][5]["op"] == 6, "Last entry must be logical OP6"

    print("test_decode_core_voice passed!")


def test_decode_additional_voice_present():
    additional = voice_params.decode_additional_voice(_make_additional_voice_bytes())

    assert additional["present"] is True
    assert additional["breath_controller"]["pitch_bias"] == 0
    assert additional["aftertouch"]["pitch_bias"] == 0
    assert additional["foot_controller_2"]["volume"] == 99
    assert additional["key_mode_mono"] is True
    assert additional["key_mode_assign"] == "Monophonic"
    assert additional["pitch_bend_range"] == 5

    print("test_decode_additional_voice_present passed!")


def test_decode_additional_voice_defaults():
    additional = voice_params.decode_additional_voice(None)

    assert additional["present"] is False
    assert additional["pitch_bend_range"] == 2
    assert additional["breath_controller"]["pitch_bias"] == 0
    assert additional["aftertouch"]["pitch_bias"] == 0
    assert additional["foot_controller_2"]["volume"] == 99
    assert additional["key_mode_assign"] == "Polyphonic"
    assert additional["pitch_eg_range"] == "8oct"

    print("test_decode_additional_voice_defaults passed!")


def test_build_voice_parameters():
    params = voice_params.build_voice_parameters(
        _make_core_voice_bytes(), _make_additional_voice_bytes()
    )
    assert params["algorithm"] == 2
    assert params["additional"]["present"] is True
    assert params["additional"]["foot_controller_2"]["volume"] == 99

    params_no_additional = voice_params.build_voice_parameters(_make_core_voice_bytes(), None)
    assert params_no_additional["additional"]["present"] is False
    assert params_no_additional["additional"]["pitch_bend_range"] == 2

    print("test_build_voice_parameters passed!")


def test_extract_voice_blocks_matches_parse_syx_file():
    """
    extract_voice_blocks() must return the same name/position/patch_type ordering as
    parse_syx_file() for the same file (this is what lets a DB row's rank among
    same-file rows map onto extract_voice_blocks()'s index — see
    database.get_voice_occurrence_index), while also carrying raw byte blocks that
    parse_syx_file() must NOT expose.
    """
    data = bytearray()
    data.extend([0xF0, 0x43, 0x00, 0x09, 0x20, 0x00])
    for v in range(32):
        voice_data = bytearray(128)
        voice_data[118:128] = f"Voice_{v + 1:02d}".ljust(10)[:10].encode('ascii')
        data.extend(voice_data)
    data.append(0x00)  # dummy checksum
    data.append(0xF7)

    temp_file = os.path.join(tempfile.gettempdir(), "test_extract_blocks.syx")
    with open(temp_file, "wb") as f:
        f.write(bytes(data))

    try:
        summary = parser.parse_syx_file(temp_file)
        blocks = parser.extract_voice_blocks(temp_file)

        assert len(summary) == len(blocks) == 32

        for s, b in zip(summary, blocks):
            assert s["name"] == b["name"]
            assert s["position"] == b["position"]
            assert s["patch_type"] == b["patch_type"]
            assert not any(k.startswith('_') for k in s), \
                "parse_syx_file() must not leak internal raw-byte keys"
            assert b["_core_bytes"] is not None and len(b["_core_bytes"]) == 128
            assert b.get("_additional_bytes") is None

        print("test_extract_voice_blocks_matches_parse_syx_file passed!")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


def run_tests():
    print("Running voice_params / parser raw-block tests...")
    test_decode_core_voice()
    test_decode_additional_voice_present()
    test_decode_additional_voice_defaults()
    test_build_voice_parameters()
    test_extract_voice_blocks_matches_parse_syx_file()
    print("All tests passed successfully!")


if __name__ == "__main__":
    run_tests()
