#!/usr/bin/env python3
"""Redline Rumble Enhanced v37 — road-length experiment.

Start from the user-confirmed v36 archive. Patch ONLY the Director LSCR 1509
beginSprite handler by multiplying mRoad.transform.scale.z by a factor of four.
The existing camera code, traffic simulation, and traffic-clone logic are
untouched. This is an experiment; it needs real-game validation.

Usage:
    python build_rr_v37.py
    python build_rr_v37.py /path/to/RedlineRumble_4K_v36_RearCamera.zip

No third-party Python dependencies are used.
"""
from __future__ import annotations

import hashlib
import copy
import json
import struct
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / 'RedlineRumble_4K_v36_RearCamera.zip'
OUT = HERE / 'RR_v37_Road.zip'
REPORT = HERE / 'RR_v37_Validation.json'

EXPECTED_GAME_SHA256 = '771cbb57bb7ee6ef2c19ce23151dd9584e2a0995f90bd43a084237b50638c4ce'
RESOURCE_ID = 1509
RESOURCE_COUNT = 1600
RESOURCE_TABLE = 136
RESOURCE_RECORD_BYTES = 20
SCALE_MULTIPLIER = 4


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def resource_data(movie: bytes, index: int) -> bytes:
    record = RESOURCE_TABLE + index * RESOURCE_RECORD_BYTES
    tag, size, offset, u1, u2 = struct.unpack_from('<4sIIII', movie, record)
    assert tag == b'rcsL', (index, tag)
    assert (u1, u2) == (0, 0)
    assert movie[offset:offset + 8] == tag + struct.pack('<I', size)
    return movie[offset + 8:offset + 8 + size]


def decode(code: bytes, allow_end: bool = False):
    result = []
    pos = 0
    while pos < len(code):
        start = pos
        raw_op = code[pos]
        pos += 1
        opcode = raw_op if raw_op < 0x40 else 0x40 + raw_op % 0x40
        size = 0 if raw_op < 0x40 else 4 if raw_op >= 0xC0 else 2 if raw_op >= 0x80 else 1
        assert pos + size <= len(code), (start, size)
        operand = int.from_bytes(code[pos:pos + size], 'big') if size else None
        pos += size
        target = start - operand if opcode == 0x54 else start + operand if opcode in (0x53, 0x55) else None
        result.append({'start': start, 'end': pos, 'opcode': opcode,
                       'operand': operand, 'width': size, 'target': target,
                       'raw': code[start:pos]})
    starts = {ins['start'] for ins in result}
    assert all(ins['target'] is None or ins['target'] in starts or
               (allow_end and ins['target'] == len(code)) for ins in result)
    return result


def encoded(opcode: int, operand: int | None = None):
    if operand is None:
        assert opcode < 0x40
        return bytes([opcode])
    assert 0x40 <= opcode < 0x80 and operand >= 0
    width = 1 if operand < 256 else 2 if operand < 65536 else 4
    return bytes([opcode + {1: 0, 2: 0x40, 4: 0x80}[width]]) + operand.to_bytes(width, 'big')


def road_hook() -> bytes:
    """Lingo equivalent: mRoad.transform.scale.z = mRoad.transform.scale.z * 4.

    All member ids are pre-existing in the game's original Lnam table:
      mRoad=396, transform=106, scale=122, z=114.
    """
    chain = encoded(0x4A, 396) + encoded(0x70, 106) + encoded(0x70, 122)
    patch = (chain + chain + encoded(0x61, 114) + encoded(0x41, SCALE_MULTIPLIER)
             + encoded(0x04) + encoded(0x62, 114))
    assert len(decode(patch)) == 10
    return patch


def inject_before(code: bytes, at: int, patch: bytes):
    original_instructions = decode(code)
    starts = {ins['start'] for ins in original_instructions}
    assert at in starts, (at, 'not an instruction boundary')
    added_instructions = decode(patch)
    assert all(ins['target'] is None for ins in added_instructions)
    new_code = bytearray()
    relocation = {}
    jumps = []
    for ins in original_instructions:
        if ins['start'] == at:
            new_code.extend(patch)
        relocation[ins['start']] = len(new_code)
        if ins['target'] is not None:
            jumps.append((len(new_code), ins))
        new_code.extend(ins['raw'])
    for at_new, ins in jumps:
        target_new = relocation[ins['target']]
        dist = at_new - target_new if ins['opcode'] == 0x54 else target_new - at_new
        assert 0 <= dist < 2 ** (8 * ins['width']), (ins, dist)
        new_code[at_new + 1:at_new + 1 + ins['width']] = dist.to_bytes(ins['width'], 'big')
    decoded_new = decode(bytes(new_code))
    assert len(decoded_new) == len(original_instructions) + len(added_instructions)
    assert all(ins['target'] is None or ins['target'] in {x['start'] for x in decoded_new} for ins in decoded_new)
    for original in original_instructions:
        matching = next((x for x in decoded_new if x['start'] == relocation[original['start']]), None)
        assert matching is not None and matching['opcode'] == original['opcode']
        assert matching['operand'] == original['operand'] or original['target'] is not None
    return bytes(new_code), len(original_instructions), len(jumps)


def rewrite_resource(original: bytes):
    # Existing v36 LSCR #1509 has two handlers, as inherited from v35.
    handler_count, handlers_offset = struct.unpack_from('>HI', original, 72)
    assert (handler_count, handlers_offset) == (2, 158)
    h0 = handlers_offset
    h1 = h0 + 46
    code0_len, code0_off = struct.unpack_from('>II', original, h0 + 4)
    code1_len, code1_off = struct.unpack_from('>II', original, h1 + 4)
    assert (code0_off, code0_len) == (250, 2501)
    assert (code1_off, code1_len) == (3024, 2924)
    code0 = original[code0_off:code0_off + code0_len]
    code1 = original[code1_off:code1_off + code1_len]
    instruction = next((i for i in decode(code0) if i['start'] == 0x013F), None)
    assert instruction is not None and instruction['opcode'] == 0x4A and instruction['operand'] == 82
    # 0x013F is the shared branch destination after both original mRoad model choices.
    new0, old_instruction_count, branch_count = inject_before(code0, 0x013F, road_hook())
    delta = len(new0) - len(code0)
    assert delta == len(road_hook())
    out = bytearray(original[:code0_off] + new0 + original[code0_off + code0_len:])

    def relocated(pos: int):
        return pos + delta if pos >= code0_off + code0_len else pos

    for field in (8, 12):
        assert struct.unpack_from('>I', original, field)[0] == len(original)
        struct.pack_into('>I', out, field, len(out))
    for field in (52, 80, 88):
        before = struct.unpack_from('>I', original, field)[0]
        assert before >= code0_off + code0_len
        struct.pack_into('>I', out, field, relocated(before))
    struct.pack_into('>I', out, h0 + 4, len(new0))
    for rec in (h0, h1):
        for offset in (8, 14, 20, 26, 38):
            val = struct.unpack_from('>I', original, rec + offset)[0]
            if val:
                assert val >= code0_off
                struct.pack_into('>I', out, rec + offset, relocated(val))
    assert out[code0_off:code0_off + len(new0)] == new0
    assert out[relocated(code1_off):relocated(code1_off) + code1_len] == code1
    assert out[relocated(code1_off) + code1_len:] == original[code1_off + code1_len:]
    assert len(out) == len(original) + delta
    return bytes(out), {'old_handler0_instructions': old_instruction_count,
                        'rebased_handler0_branches': branch_count,
                        'injected_before_original_bytecode_offset': '0x013f',
                        'added_instructions': len(decode(road_hook())),
                        'added_bytes': delta,
                        'other_handler_bytewise_unchanged': True}


def main():
    with zipfile.ZipFile(BASE) as archive:
        assert archive.testzip() is None
        movie = archive.read('game.dir')
        assert digest(movie) == EXPECTED_GAME_SHA256, 'Unexpected base game.dir; use confirmed v36'
        old_resource = resource_data(movie, RESOURCE_ID)
        new_resource, audit = rewrite_resource(old_resource)
        result = bytearray(movie)
        offset = len(result)
        result.extend(b'rcsL' + struct.pack('<I', len(new_resource)) + new_resource)
        struct.pack_into('<II', result, RESOURCE_TABLE + RESOURCE_ID * RESOURCE_RECORD_BYTES + 4, len(new_resource), offset)
        struct.pack_into('<I', result, 4, len(result) - 8)
        assert resource_data(result, RESOURCE_ID) == new_resource
        unchanged_records = 0
        for index in range(RESOURCE_COUNT):
            if index != RESOURCE_ID:
                begin = RESOURCE_TABLE + index * RESOURCE_RECORD_BYTES
                assert result[begin:begin + RESOURCE_RECORD_BYTES] == movie[begin:begin + RESOURCE_RECORD_BYTES]
                unchanged_records += 1
        assert resource_data(result, 1506) == resource_data(movie, 1506), 'v36 camera changed'
        # Extract independently: original clone hooks stay in both 1509 handlers.
        assert b'\x8a\x01\xb6' in new_resource, 'visual model list no longer present'
        result_bytes = bytes(result)
        readme = (
            'Redline Rumble Enhanced v37 — ROAD DISTANCE EXPERIMENT\n\n'
            'Based directly on the user-confirmed v36 build.\n'
            'The road model\'s existing Z scale is multiplied by 4 at startup.\n'
            'This may extend the visible surface but may also affect texture scaling,\n'
            'road placement, or Director rendering; only actual gameplay can prove it works.\n'
            'Cars, rear visual clones, spawning, camera controls, HUD and collision logic\n'
            'are intentionally unchanged. The 60 FPS and fullscreen settings are unchanged.\n'
            'Revert to v36 immediately if the road or racing behaviour looks wrong.\n'
        )
        with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as target:
            for member in archive.infolist():
                if member.filename.startswith('README v') and member.filename.endswith('.txt'):
                    continue
                payload = result_bytes if member.filename == 'game.dir' else archive.read(member.filename)
                target.writestr(copy.copy(member), payload)
            target.writestr('README v37.txt', readme)
        with zipfile.ZipFile(OUT) as tested:
            assert tested.testzip() is None
            assert tested.read('game.dir') == result_bytes
            for member in archive.namelist():
                if member == 'game.dir' or (member.startswith('README v') and member.endswith('.txt')):
                    continue
                assert tested.read(member) == archive.read(member), member
    report = {
        'status': 'STATIC VALIDATION PASSED — RUNTIME UNTESTED',
        'base': str(BASE), 'output': str(OUT),
        'base_game_sha256': EXPECTED_GAME_SHA256,
        'new_game_sha256': digest(result_bytes),
        'archive_sha256': digest(OUT.read_bytes()),
        'director_resource_modified': RESOURCE_ID,
        'other_resource_map_records_unchanged': unchanged_records,
        'v36_camera_resource_1506_identical': True,
        'rear_traffic_clone_code_retained': True,
        'road_scale_z_multiplier': SCALE_MULTIPLIER,
        'simulation_spawning_collision_not_modified': True,
        'forward_traffic_popin_fixed': False,
        'road_horizon_fixed': 'unverified in game',
        **audit
    }
    REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()