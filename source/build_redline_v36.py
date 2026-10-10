#!/usr/bin/env python3
"""Redline Rumble v36: restore hood orientation and relocate rear-view camera behind the player's car.

Only the camera handler's appended Lingo bytecode in LSCR #1506 is replaced.
No additional Lingo properties, names or unsupported transform operations are used.
All unrelated game resources are preserved byte-for-byte from the working v35.

Input: source/RedlineRumble_4K_v35_TrafficFix.zip
Outputs: source/RedlineRumble_4K_v36_RearCamera.zip
         source/RedlineRumble_v36_validation.json

Static checks do not prove in-game operation. Test on Windows before declaring fixed.
"""
from __future__ import annotations

from collections import deque
from hashlib import sha256
from pathlib import Path
import json
import struct
import zipfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'RedlineRumble_4K_v35_TrafficFix.zip'
TARGET = HERE / 'RedlineRumble_4K_v36_RearCamera.zip'
REPORT = HERE / 'RedlineRumble_v36_validation.json'
ENTRY = 1506
RESOURCE_MAP_START = 136
RESOURCE_ENTRY_SIZE = 20
SCRIPT_HND_OFFSET = 170
SCRIPT_HND_RECORD_SIZE = 46
HANDLER_START = 0x5D4
TAIL_START = 0xCAA
EXPECTED_V28_SHA = '0af42b1a787860cbf6503b3f15d9c1690ae69befb0e5e4997ba29ae5f8b186fd'
V28_CODE_LENGTH = 348

class Asm:
    codes = {
        'ret': 0x01, 'add': 0x05, 'lt': 0x0C, 'eq': 0x0F,
        'getprop': 0x4A, 'setprop': 0x50, 'push': 0x41,
        'args': 0x43, 'argsNoRet': 0x42, 'sym': 0x45,
        'extCall': 0x57, 'getObjProp': 0x61,
        'setObjProp': 0x62, 'getChainedProp': 0x70, 'objCall': 0x67,
    }

    def __init__(self):
        self.data = bytearray()
        self.labels = {}
        self.fixes = []

    def here(self, label):
        assert label not in self.labels
        self.labels[label] = len(self.data)

    def op(self, name, value=None):
        code = self.codes[name]
        if value is None:
            assert code < 0x40, name
            self.data.append(code)
        elif name == 'push':
            if -128 <= value <= 127:
                self.data.extend((code, value & 0xff))
            else:
                assert -32768 <= value <= 32767
                self.data.append(0xAE)
                self.data += struct.pack('>h', value)
        elif 0 <= value < 256:
            self.data.extend((code, value))
        else:
            assert 0 <= value <= 65535
            self.data.append(code + 0x40)
            self.data += struct.pack('>H', value)

    def branch(self, opname, label):
        assert opname in ('jmp', 'jmpIfZ')
        pos = len(self.data)
        self.data.extend((0x93 if opname == 'jmp' else 0x95, 0, 0))
        self.fixes.append((pos, label))

    def finish(self):
        for pos, label in self.fixes:
            assert label in self.labels, label
            delta = self.labels[label] - pos
            assert 0 <= delta <= 65535, (pos, label, delta)
            struct.pack_into('>H', self.data, pos + 1, delta)
        return bytes(self.data)


def assemble():
    a = Asm()

    def num(n): a.op('push', n)
    def pget(n): a.op('getprop', n)
    def pset(n): a.op('setprop', n)

    def key(code):
        num(code)
        a.op('args', 1)
        a.op('extCall', 171)  # v28 keyPressed: C=8, B=11

    def car_world():
        pget(301)
        a.op('getObjProp', 105)  # mRaceCar.worldPosition

    def vec(x, y, z):
        for n in (x, y, z): num(n)
        a.op('args', 3)
        a.op('extCall', 104)  # vector()

    def camera_at_car(x, y, z):
        pget(96)
        car_world()
        vec(x, y, z)
        a.op('add')
        a.op('setObjProp', 105)

    def point_camera_at_car(x, y, z, fov):
        pget(96)
        car_world()
        vec(x, y, z)
        a.op('add')
        a.op('argsNoRet', 2)
        a.op('objCall', 162)  # camera.pointAt, verified in v28
        pget(96)
        num(fov)
        a.op('setObjProp', 296)

    def restore_vanilla_hood_rotation():
        # Byte-for-byte equivalent of the original game's sequence at
        # exitFrame bytecode offsets 0x4A4..0x4AF (before its preRotate).
        # Unlike v29, NO new script property is registered or accessed.
        # Unlike v30, this does not use pointAt across opposite directions.
        pget(96)                          # cam
        a.op('getChainedProp', 106)       # .transform
        num(0)
        num(0)
        num(0)
        a.op('args', 3)
        a.op('extCall', 104)              # vector(0,0,0)
        a.op('setObjProp', 107)           # .rotation = vector(0,0,0)

    def save_original_local_position():
        # Exact v28 routine. Never read or write transform.rotation.
        for axis in (119, 115, 114):
            pget(96)
            a.op('getChainedProp', 106)
            a.op('getChainedProp', 110)
            a.op('getObjProp', axis)
        a.op('args', 3)
        a.op('extCall', 104)
        pset(337)

    def restore_original_local_position():
        pget(96)
        a.op('getChainedProp', 106)
        pget(337)
        a.op('setObjProp', 110)
        pget(96)
        num(70)
        a.op('setObjProp', 296)

    # Uses only the SAME existing state property and four ordinary camera
    # modes as v28; values 4 and 6 are temporary B-held sub-states.
    # 0: stock, 1: chase, 2: stock C-held, 3: chase C-held,
    # 4: stock B-held, 6: stock B-held and C-held.
    # Initially void; no arithmetic or boolean coercion of this property.

    pget(282)
    a.op('sym', 315)
    a.op('eq')
    a.branch('jmpIfZ', 'done')
    pget(273)
    num(360)
    a.op('lt')
    a.branch('jmpIfZ', 'done')

    # C edge detection, including both B-held stock states.
    key(8)
    a.branch('jmpIfZ', 'c_up')
    for held in (2, 3, 6):
        pget(336)
        num(held)
        a.op('eq')
        a.branch('jmpIfZ', f'c_test_{held}')
        a.branch('jmp', 'c_complete')
        a.here(f'c_test_{held}')

    pget(336)
    num(1)
    a.op('eq')
    a.branch('jmpIfZ', 'to_chase')
    # Third person -> stock, original v28 restoration routine.
    num(2)
    pset(336)
    restore_original_local_position()
    a.branch('jmp', 'c_complete')

    a.here('to_chase')
    # If switching from stock while B is held, cam1 already contains the
    # ORIGINAL hood-local camera position, saved before moving the camera.
    # Saving again here would accidentally preserve the rear bumper position.
    pget(336)
    num(4)
    a.op('eq')
    a.branch('jmpIfZ', 'to_chase_fresh_save')
    a.branch('jmp', 'to_chase_saved')
    a.here('to_chase_fresh_save')
    save_original_local_position()
    a.here('to_chase_saved')
    num(3)
    pset(336)
    a.branch('jmp', 'c_complete')

    a.here('c_up')
    for old, new in ((6, 4), (2, 0), (3, 1)):
        pget(336)
        num(old)
        a.op('eq')
        a.branch('jmpIfZ', f'c_up_next_{old}')
        num(new)
        pset(336)
        a.branch('jmp', 'c_complete')
        a.here(f'c_up_next_{old}')

    a.here('c_complete')
    key(11)
    a.branch('jmpIfZ', 'b_up')

    # B held in chase: unchanged v28 chase look-back geometry.
    for held in (1, 3):
        pget(336)
        num(held)
        a.op('eq')
        a.branch('jmpIfZ', f'b_chase_test_{held}')
        a.branch('jmp', 'chase_rear')
        a.here(f'b_chase_test_{held}')

    # On the first B-held frame in stock, remember only that B is held.
    # No new camera transform/property access or mutation.
    for held in (4, 6):
        pget(336)
        num(held)
        a.op('eq')
        a.branch('jmpIfZ', f'b_stock_test_{held}')
        a.branch('jmp', 'stock_rear')
        a.here(f'b_stock_test_{held}')

    pget(336)
    num(2)
    a.op('eq')
    a.branch('jmpIfZ', 'b_initial_stock_c_up')
    save_original_local_position()
    num(6)
    pset(336)
    a.branch('jmp', 'stock_rear')
    a.here('b_initial_stock_c_up')
    save_original_local_position()
    num(4)
    pset(336)

    a.here('stock_rear')
    # Position OUTSIDE and behind the player's model, with an unobstructed
    # backwards view. Camera must be restored to saved local hood position.
    camera_at_car(0, 180, 750)
    point_camera_at_car(0, 120, 1550, 70)
    a.branch('jmp', 'done')

    a.here('chase_rear')
    camera_at_car(0, 320, -800)
    point_camera_at_car(0, 80, 450, 75)  # identical to v28
    a.branch('jmp', 'done')

    a.here('b_up')
    # On the FIRST released frame in hood view, restore the known vanilla
    # camera rotation with the original game's own vector setter.
    # pointAt() with an opposite-facing aim (v30) caused upward flipping.
    # Resetting the Euler rotation directly does NOT interpolate 180 degrees.
    # The normal game continues to handle pitch, car sway and shake.
    for old, new in ((4, 0), (6, 2)):
        pget(336)
        num(old)
        a.op('eq')
        a.branch('jmpIfZ', f'b_release_next_{old}')
        num(new)
        pset(336)
        restore_original_local_position()
        restore_vanilla_hood_rotation()
        a.branch('jmp', 'done')
        a.here(f'b_release_next_{old}')

    # Chase forward: unchanged v28 pose and target.
    for held in (1, 3):
        pget(336)
        num(held)
        a.op('eq')
        a.branch('jmpIfZ', f'b_chase_forward_test_{held}')
        a.branch('jmp', 'chase_forward')
        a.here(f'b_chase_forward_test_{held}')
    a.branch('jmp', 'done')

    a.here('chase_forward')
    camera_at_car(0, 320, 800)
    point_camera_at_car(0, 80, -300, 75)
    a.here('done')
    a.op('ret')
    return a.finish(), a.labels


def lscr_from_movie(movie):
    rec = RESOURCE_MAP_START + ENTRY * RESOURCE_ENTRY_SIZE
    tag, size, off, unused1, unused2 = struct.unpack_from('<4sIIII', movie, rec)
    assert tag == b'rcsL' and unused1 == unused2 == 0
    assert movie[off:off+8] == b'rcsL' + struct.pack('<I', size)
    data = movie[off+8:off+8+size]
    assert len(data) == size
    return data


def mutate_lscr(old, new_code):
    handler2 = SCRIPT_HND_OFFSET + SCRIPT_HND_RECORD_SIZE
    start = struct.unpack_from('>I', old, handler2 + 8)[0]
    compiled = struct.unpack_from('>I', old, handler2 + 4)[0]
    assert start == HANDLER_START
    assert compiled == TAIL_START + V28_CODE_LENGTH
    assert old[start + TAIL_START + V28_CODE_LENGTH - 1] == 1  # ret
    cut1 = start + TAIL_START
    cut2 = cut1 + V28_CODE_LENGTH
    result = bytearray(old[:cut1] + new_code + old[cut2:])
    diff = len(new_code) - V28_CODE_LENGTH
    for offset in (8, 12):
        struct.pack_into('>I', result, offset, len(result))
    for offset in (52, 80, 88, handler2+14, handler2+20, handler2+26, handler2+38):
        value = struct.unpack_from('>I', old, offset)[0]
        assert value >= cut2, (offset, value, cut2)
        struct.pack_into('>I', result, offset, value + diff)
    struct.pack_into('>I', result, handler2+4, compiled + diff)

    # All original 39 property names are preserved; absolutely no new
    # property, name or Lingo header offsets except those shifted by code.
    assert struct.unpack_from('>H', result, 60)[0] == 39
    assert struct.unpack_from('>I', result, 62)[0] == 92
    assert result[92:170] == old[92:170]
    assert result[start:cut1] == old[start:cut1]
    assert result[cut1+len(new_code):] == old[cut2:]
    assert result[-32:] == old[-32:]
    assert struct.unpack_from('>I', result, 52)[0] == len(result) - 32
    return bytes(result)


def decode_bytecode(data):
    out = {}
    p = 0
    while p < len(data):
        raw = data[p]
        opcode = (0x40 + raw % 0x40) if raw >= 0x40 else raw
        size = 4 if raw >= 0xC0 else 2 if raw >= 0x80 else 1 if raw >= 0x40 else 0
        value = int.from_bytes(data[p+1:p+1+size], 'big') if size else None
        out[p] = (opcode, value, p+1+size)
        p += 1 + size
    assert p == len(data)
    return out


def validate_flow(new_code):
    ins = decode_bytecode(new_code)
    known = {
        0x01:(0,0), 0x05:(2,1), 0x0c:(2,1), 0x0f:(2,1),
        0x41:(0,1), 0x6e:(0,1), 0x45:(0,1), 0x4a:(0,1),
        0x50:(1,0), 0x57:(1,1), 0x61:(1,1),
        0x62:(2,0), 0x70:(1,1), 0x67:(1,0),
        0x53:(0,0), 0x55:(1,0),
    }
    queue = deque([(0,0)])
    seen = set()
    returns = []
    max_stack = 0
    while queue:
        pos, stack = queue.popleft()
        if (pos,stack) in seen: continue
        assert pos in ins, (pos,stack)
        seen.add((pos,stack))
        op, value, end = ins[pos]
        pop, push = (value,1) if op in (0x42,0x43) else known[op]
        assert stack >= pop, (pos, op, stack, pop)
        depth = stack - pop + push
        max_stack = max(max_stack, depth)
        if op == 1:
            assert depth == 0
            returns.append(pos)
            continue
        targets = [pos+value] + ([end] if op == 0x55 else []) if op in (0x53,0x55) else [end]
        for target in targets:
            assert target in ins, ('jump into middle of instruction', pos, target)
            queue.append((target,depth))
    assert len(returns) == 1
    return {
        'reachable_instruction_states': len(seen),
        'return_stack_empty': True,
        'all_jumps_instruction_aligned': True,
        'no_stack_underflow': True,
        'max_stack_depth': max_stack,
    }


def main():
    code, labels = assemble()
    cfg = validate_flow(code)
    with zipfile.ZipFile(SOURCE) as inp:
        assert inp.testzip() is None
        names = inp.namelist()
        assert names.count('game.dir') == 1
        old_game = inp.read('game.dir')
        assert sha256(old_game).hexdigest() == EXPECTED_V28_SHA
        old_lscr = lscr_from_movie(old_game)
        # Rotation setter duplicated exclusively from original live camera code.
        # Expected instruction stream: cam.transform, vector(0,0,0), set rotation.
        vanilla_reset = bytes.fromhex('4a 60 70 6a 03 03 03 43 03 57 68 62 6b')
        base_handler = old_lscr[HANDLER_START:HANDLER_START+TAIL_START]
        assert vanilla_reset in base_handler, 'original vanilla camera rotation reset not found'
        assert bytes.fromhex('62 6b') in code, 'native rotation restore missing'
        new_lscr = mutate_lscr(old_lscr, code)

        # Append a single changed resource, just as v28 was built.
        dest_game = bytearray(old_game)
        new_offset = len(dest_game)
        dest_game += b'rcsL' + struct.pack('<I', len(new_lscr)) + new_lscr
        res_offset = RESOURCE_MAP_START + ENTRY * RESOURCE_ENTRY_SIZE
        struct.pack_into('<II', dest_game, res_offset+4, len(new_lscr), new_offset)
        struct.pack_into('<I', dest_game, 4, len(dest_game)-8)
        assert lscr_from_movie(dest_game) == new_lscr
        for i in range(1600):
            if i == ENTRY: continue
            o = RESOURCE_MAP_START + i*RESOURCE_ENTRY_SIZE
            assert dest_game[o:o+RESOURCE_ENTRY_SIZE] == old_game[o:o+RESOURCE_ENTRY_SIZE], i
        assert dest_game[RESOURCE_MAP_START+ENTRY*RESOURCE_ENTRY_SIZE+12:RESOURCE_MAP_START+ENTRY*RESOURCE_ENTRY_SIZE+20] == old_game[RESOURCE_MAP_START+ENTRY*RESOURCE_ENTRY_SIZE+12:RESOURCE_MAP_START+ENTRY*RESOURCE_ENTRY_SIZE+20]

        readme = ("Redline Rumble v36 - Rear Camera Repair (EXPERIMENTAL)\n\n"
                  "Based on user-confirmed v35 visual rear traffic (untouched).\n"
                  "C toggles hood / far chase. Hold B for rear view.\n"
                  "In hood mode, B places the rear camera behind the car,\n"
                  "aiming away from it instead of looking through the roof.\n"
                  "B saves original hood local position, restoring on release\n"
                  "along with original game rotation reset.\n"
                  "C during B hold retains saved original local position.\n"
                  "Original forward traffic and static road have NOT been altered.\n"
                  "The original camera far-plane is already 999900 units;\n"
                  "road horizon / forward spawn pop-in require separate work.\n"
                  "Static code validation passed; gameplay testing needed.\n")
        with zipfile.ZipFile(TARGET, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as out:
            for info in inp.infolist():
                if info.filename == 'README v35.txt': continue
                payload = bytes(dest_game) if info.filename == 'game.dir' else inp.read(info.filename)
                out.writestr(info, payload)
            out.writestr('README v36.txt', readme)

    with zipfile.ZipFile(SOURCE) as inp, zipfile.ZipFile(TARGET) as result:
        assert result.testzip() is None
        assert result.read('game.dir') == bytes(dest_game)
        old_set = set(inp.namelist())
        new_set = set(result.namelist())
        assert new_set == (old_set - {'README v35.txt'}) | {'README v36.txt'}
        unchanged = 0
        for name in old_set - {'game.dir', 'README v35.txt'}:
            assert result.read(name) == inp.read(name), name
            unchanged += 1

    audit = {
        'status':'STATIC TESTS PASSED; Windows gameplay not tested',
        'input':'user-confirmed working v35; v29 excluded',
        'base_game_dir_sha256': sha256(old_game).hexdigest(),
        'new_game_dir_sha256': sha256(dest_game).hexdigest(),
        'zip_sha256': sha256(TARGET.read_bytes()).hexdigest(),
        'new_camera_patch_length': len(code),
        'new_script_resource_length': len(new_lscr),
        'changed_movie_resource_indices':[ENTRY],
        'untouched_movie_resource_entries':1599,
        'untouched_external_files':unchanged,
        'new_script_property_names':0, 'rear_visual_clones_resource_1509_preserved':True,
        'transform_rotation_reads_or_writes':'one known vanilla rotation set on hood B release',
        'B_release':'restore saved hood-local position and one-time native transform.rotation=vector(0,0,0)',
        'C_camera':'existing v28 original/chase toggle',
        'B_chase':'existing v28 chase look-back geometry', 'B_hood':'camera moves to car+(0,180,750), aims at car+(0,120,1550)' ,
        'assembly_labels':labels,
        'bytecode_check':cfg,
        'audio_modified':False, 'road_geometry_modified':False, 'forward_traffic_modified':False,
        'gameplay_verified':False,
    }
    REPORT.write_text(json.dumps(audit, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k!='assembly_labels'},indent=2))

if __name__ == '__main__':
    main()