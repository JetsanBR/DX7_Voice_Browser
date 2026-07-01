"""
Pure byte-level decoders for DX7/DX7s/DX7II voice parameters.

This module knows nothing about files, the database, or HTTP — it only turns raw
SysEx byte blocks into structured parameter dicts. It's the reusable foundation for
any future feature that needs full voice parameters (the Voice Parameters page,
export, comparison, editing, etc.); parser.py is responsible for finding the right
bytes inside a .syx file (see parser.extract_voice_blocks()).

Byte offsets and bit layouts below follow
design_handoff_voice_parameters/yamaha_dx7s_sysex_specification_v2_1.md sections 5
(core 128-byte VMEM voice) and 6 (additional 35-byte AMEM voice) exactly.
"""

from parser import clean_voice_name

CORE_VOICE_SIZE = 128
ADDITIONAL_VOICE_SIZE = 35

OP_CURVE_NAMES = ['-LIN', '-EXP', '+LIN', '+EXP']
LFO_WAVE_NAMES = ['TRI', 'SAW DOWN', 'SAW UP', 'SQUARE', 'SINE', 'S/HOLD']
PITCH_BEND_MODE_NAMES = ['Normal', 'Lowest', 'Highest', 'Key On']
PEG_RANGE_NAMES = {0: '8oct', 1: '4oct', 2: '1oct', 3: '1/2oct'}

# Chromatic scale starting at A, used for the keyboard-scaling break point (spec §5-1,
# byte 8 of each operator): value 0 = A-1 ... value 99 = C8.
_NOTE_LETTERS_FROM_A = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']

# Chromatic scale starting at C, used for the voice transpose (spec §5-2, byte 117):
# value 24 = C3 (center), range 0-48 = C1..C5.
_NOTE_LETTERS_FROM_C = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Which operator(s) are wired to the audio output (carriers) and which single
# operator carries the self-feedback loop, per algorithm (1-32). This is standard
# published DX7 algorithm-routing data, NOT part of the sysex byte-offset spec (the
# sysex only stores the algorithm *number* and feedback *amount* — never which
# operator the feedback loop sits on, since that's fixed per algorithm). Reconstructed
# from general DX7 reference knowledge; only algorithm 2 has been cross-checked here
# against the spec's own worked example (MellowHorn, §8) and the approved mockup.
# TODO: spot-check the remaining 31 entries against the official Yamaha DX7 algorithm
# chart before relying on this for anything beyond the Voice Parameters page's
# decorative operator-role coloring / feedback icon.
DX7_ALGORITHMS = {
    1:  {'carriers': [1, 4],             'feedback_op': 6},
    2:  {'carriers': [1, 2],             'feedback_op': 2},
    3:  {'carriers': [1, 4],             'feedback_op': 6},
    4:  {'carriers': [1, 4],             'feedback_op': 4},
    5:  {'carriers': [1, 3, 5],          'feedback_op': 6},
    6:  {'carriers': [1, 3, 5],          'feedback_op': 6},
    7:  {'carriers': [1, 2, 4],          'feedback_op': 2},
    8:  {'carriers': [1, 2, 4],          'feedback_op': 2},
    9:  {'carriers': [1, 2, 4],          'feedback_op': 2},
    10: {'carriers': [1, 4],             'feedback_op': 4},
    11: {'carriers': [1, 4],             'feedback_op': 6},
    12: {'carriers': [1, 2],             'feedback_op': 2},
    13: {'carriers': [1, 2],             'feedback_op': 2},
    14: {'carriers': [1, 2],             'feedback_op': 2},
    15: {'carriers': [1, 2],             'feedback_op': 2},
    16: {'carriers': [1],                'feedback_op': 2},
    17: {'carriers': [1],                'feedback_op': 2},
    18: {'carriers': [1],                'feedback_op': 3},
    19: {'carriers': [1, 4, 5],          'feedback_op': 1},
    20: {'carriers': [1, 2, 3],          'feedback_op': 3},
    21: {'carriers': [1, 2, 3, 4],       'feedback_op': 3},
    22: {'carriers': [1, 2, 3, 4, 5],    'feedback_op': 1},
    23: {'carriers': [1, 3, 5],          'feedback_op': 1},
    24: {'carriers': [1, 2, 3, 4],       'feedback_op': 1},
    25: {'carriers': [1, 2, 3],          'feedback_op': 1},
    26: {'carriers': [1, 3],             'feedback_op': 1},
    27: {'carriers': [1, 3],             'feedback_op': 3},
    28: {'carriers': [1, 3, 6],          'feedback_op': 6},
    29: {'carriers': [1, 2, 4, 5],       'feedback_op': 5},
    30: {'carriers': [1, 2, 4, 5],       'feedback_op': 6},
    31: {'carriers': [1, 2, 3, 4, 5],    'feedback_op': 5},
    32: {'carriers': [1, 2, 3, 4, 5, 6], 'feedback_op': 6},
}


def get_algorithm_info(algorithm_number: int) -> dict:
    """Returns {'carriers': [...], 'feedback_op': int} for a 1-32 algorithm number,
    falling back to a safe default (OP1 as sole carrier/feedback) if out of range."""
    return DX7_ALGORITHMS.get(algorithm_number, {'carriers': [1], 'feedback_op': 1})


def _breakpoint_note_name(index: int) -> str:
    """Converts a 0-99 keyboard-scaling break point value to its note name (A-1..C8)."""
    letter = _NOTE_LETTERS_FROM_A[index % 12]
    octave = -1 + (index + 9) // 12
    return f"{letter}{octave}"


def _transpose_note_name(value: int) -> str:
    """Converts a 0-48 transpose value (24 = C3) to its note name (C1..C5)."""
    semitone_offset = value - 24
    letter = _NOTE_LETTERS_FROM_C[semitone_offset % 12]
    octave = 3 + (semitone_offset // 12)
    return f"{letter}{octave}"


def _decode_operator(op_bytes: bytes) -> dict:
    """Decodes one 17-byte operator block (spec §5-1)."""
    b8, b9, b10, b11, b12, b13 = op_bytes[8], op_bytes[9], op_bytes[10], op_bytes[11], op_bytes[12], op_bytes[13]
    b15 = op_bytes[15]

    left_curve = b11 & 0x03
    right_curve = (b11 >> 2) & 0x03
    rate_scaling = b12 & 0x07
    detune_raw = (b12 >> 3) & 0x0F
    amp_mod_sens = b13 & 0x03
    vel_sens = (b13 >> 2) & 0x07
    osc_mode = b15 & 0x01
    freq_coarse = (b15 >> 1) & 0x1F

    return {
        'eg_rate': [op_bytes[0], op_bytes[1], op_bytes[2], op_bytes[3]],
        'eg_level': [op_bytes[4], op_bytes[5], op_bytes[6], op_bytes[7]],
        'break_point': b8,
        'break_point_name': _breakpoint_note_name(b8),
        'left_depth': b9,
        'right_depth': b10,
        'left_curve': left_curve,
        'left_curve_name': OP_CURVE_NAMES[left_curve],
        'right_curve': right_curve,
        'right_curve_name': OP_CURVE_NAMES[right_curve],
        'rate_scaling': rate_scaling,
        'detune': detune_raw - 7,
        'amp_mod_sens': amp_mod_sens,
        'vel_sens': vel_sens,
        'level': op_bytes[14],
        'osc_mode': 'Fixed' if osc_mode else 'Ratio',
        'freq_coarse': freq_coarse,
        'freq_fine': op_bytes[16],
    }


def decode_core_voice(core_bytes: bytes) -> dict:
    """Decodes a 128-byte VMEM core voice record (spec §5) into a structured dict.

    Operators are returned as a list of 6 dicts in logical OP1..OP6 order (each with
    an 'op' key = 1..6); the raw storage order is OP6 first, OP1 last, per spec §5.
    """
    if core_bytes is None or len(core_bytes) < CORE_VOICE_SIZE:
        raise ValueError(f"decode_core_voice requires a {CORE_VOICE_SIZE}-byte core voice block")

    operators = []
    for logical_op in range(1, 7):
        storage_index = 6 - logical_op  # OP1 -> storage slot 5, OP6 -> storage slot 0
        op_bytes = core_bytes[storage_index * 17: (storage_index + 1) * 17]
        op = _decode_operator(op_bytes)
        op['op'] = logical_op
        operators.append(op)

    algorithm = (core_bytes[110] & 0x1F) + 1
    b111 = core_bytes[111]
    feedback = b111 & 0x07
    osc_key_sync = bool((b111 >> 3) & 0x01)

    b116 = core_bytes[116]
    lfo_sync = bool(b116 & 0x01)
    lfo_wave = (b116 >> 1) & 0x07
    lfo_pms = (b116 >> 4) & 0x07

    transpose = core_bytes[117] & 0x3F

    algo_info = get_algorithm_info(algorithm)

    return {
        'name': clean_voice_name(core_bytes[118:128]),
        'algorithm': algorithm,
        'algorithm_carriers': algo_info['carriers'],
        'algorithm_feedback_op': algo_info['feedback_op'],
        'feedback': feedback,
        'osc_key_sync': osc_key_sync,
        'operators': operators,
        'pitch_eg': {
            'rate': list(core_bytes[102:106]),
            'level': list(core_bytes[106:110]),
        },
        'lfo': {
            'speed': core_bytes[112],
            'delay': core_bytes[113],
            'pmd': core_bytes[114],
            'amd': core_bytes[115],
            'sync': lfo_sync,
            'wave': lfo_wave,
            'wave_name': LFO_WAVE_NAMES[lfo_wave] if lfo_wave < len(LFO_WAVE_NAMES) else 'UNKNOWN',
            'pitch_mod_sensitivity': lfo_pms,
        },
        'transpose': transpose,
        'transpose_name': _transpose_note_name(transpose),
    }


def _decode_additional_bytes(b: bytes) -> dict:
    """Decodes a real 35-byte AMEM additional-voice record (spec §6). Shared by
    decode_additional_voice() and _default_additional_voice() (the latter runs this
    over a synthetic all-defaults byte block so both paths return the exact same
    shape from one source of truth)."""
    op_scaling_mode = [(b[0] >> (op - 1)) & 0x01 for op in range(1, 7)]  # index0=OP1..index5=OP6

    # Per spec §6: byte1 bits0-2/3-5 = OP5/OP6, byte2 = OP3/OP4, byte3 = OP1/OP2.
    am_sens_lookup = {1: (3, 0), 2: (3, 3), 3: (2, 0), 4: (2, 3), 5: (1, 0), 6: (1, 3)}
    op_am_sens = [(b[am_sens_lookup[op][0]] >> am_sens_lookup[op][1]) & 0x07 for op in range(1, 7)]

    peg_range_code = b[4] & 0x03
    lfo_key_trigger_multi = bool((b[4] >> 2) & 0x01)
    peg_velocity = bool((b[4] >> 3) & 0x01)
    random_pitch = (b[4] >> 4) & 0x07

    key_mode_mono = bool(b[5] & 0x01)
    unison_on = bool((b[5] >> 1) & 0x01)
    pitch_bend_range = (b[5] >> 2) & 0x1F

    pitch_bend_step = b[6] & 0x0F
    pitch_bend_mode_code = (b[6] >> 4) & 0x03

    portamento_mode_code = b[7] & 0x01
    portamento_step = (b[7] >> 1) & 0x1F

    if unison_on:
        key_mode_assign = 'Unison Mono' if key_mode_mono else 'Unison Poly'
    else:
        key_mode_assign = 'Monophonic' if key_mode_mono else 'Polyphonic'

    return {
        'present': True,
        'operator_scaling_mode': op_scaling_mode,
        'operator_scaling_mode_name': ['Fractional' if v else 'Normal' for v in op_scaling_mode],
        'operator_am_sens': op_am_sens,
        'pitch_eg_range_code': peg_range_code,
        'pitch_eg_range': PEG_RANGE_NAMES.get(peg_range_code, '8oct'),
        'pitch_eg_velocity': peg_velocity,
        'pitch_eg_rate_scaling': b[24] & 0x07,
        'lfo_key_trigger': 'Multi' if lfo_key_trigger_multi else 'Single',
        'random_pitch': random_pitch,
        'key_mode_mono': key_mode_mono,
        'unison': unison_on,
        'key_mode_assign': key_mode_assign,
        'unison_detune': b[34] & 0x07,
        'pitch_bend_range': pitch_bend_range,
        'pitch_bend_step': pitch_bend_step,
        'pitch_bend_mode_code': pitch_bend_mode_code,
        'pitch_bend_mode': PITCH_BEND_MODE_NAMES[pitch_bend_mode_code],
        'portamento_mode_code': portamento_mode_code,
        'portamento_mode': 'Fingered/Full-Time' if portamento_mode_code else 'Sus-Key/Retain-Follow',
        'portamento_step': portamento_step,
        'portamento_time': b[8],
        'mod_wheel': {'pitch': b[9], 'amp': b[10], 'eg_bias': b[11]},
        'foot_controller_1': {'pitch': b[12], 'amp': b[13], 'eg_bias': b[14], 'volume': b[15]},
        'breath_controller': {'pitch': b[16], 'amp': b[17], 'eg_bias': b[18], 'pitch_bias': b[19] - 50},
        'aftertouch': {'pitch': b[20], 'amp': b[21], 'eg_bias': b[22], 'pitch_bias': b[23] - 50},
        'foot_controller_2': {'pitch': b[26], 'amp': b[27], 'eg_bias': b[28], 'volume': b[29]},
        'midi_controller': {'pitch': b[30], 'amp': b[31], 'eg_bias': b[32], 'volume': b[33]},
        'fc1_as_cs1': bool((b[34] >> 3) & 0x01),
    }


def _build_default_additional_bytes() -> bytes:
    """Builds a synthetic 35-byte block encoding the documented power-on defaults
    from spec §6 (all zero except where a non-zero default is explicitly listed)."""
    b = bytearray(ADDITIONAL_VOICE_SIZE)
    b[5] = 2 << 2   # Pitch Bend Range default = 2 (bits 2-6)
    b[19] = 50      # Breath Controller Pitch Bias default = neutral (stored-50 = 0)
    b[23] = 50      # Aftertouch Pitch Bias default = neutral (stored-50 = 0)
    b[29] = 99      # Foot Controller 2 Volume default = 99
    return bytes(b)


_DEFAULT_ADDITIONAL_BYTES = _build_default_additional_bytes()


def _default_additional_voice() -> dict:
    result = _decode_additional_bytes(_DEFAULT_ADDITIONAL_BYTES)
    result['present'] = False
    return result


def decode_additional_voice(additional_bytes) -> dict:
    """Decodes a 35-byte AMEM additional-voice record (spec §6). If additional_bytes
    is None (plain DX7 mkI dump with no $06 block for this voice), returns the
    documented power-on defaults instead, with 'present': False."""
    if additional_bytes is None:
        return _default_additional_voice()
    if len(additional_bytes) < ADDITIONAL_VOICE_SIZE:
        raise ValueError(f"decode_additional_voice requires a {ADDITIONAL_VOICE_SIZE}-byte block")
    return _decode_additional_bytes(additional_bytes)


def build_voice_parameters(core_bytes: bytes, additional_bytes=None) -> dict:
    """Combines decode_core_voice() + decode_additional_voice() into the full voice
    parameter model consumed by the Voice Parameters API/page."""
    core = decode_core_voice(core_bytes)
    core['additional'] = decode_additional_voice(additional_bytes)
    return core
