#!/usr/bin/env python3
"""v43: bounded directional rear-visual reuse; native gameplay unverified.

Build from hash-locked user-owned v28/v36 archives. Historical emitters are
loaded in an isolated module; v42 and all historical builders stay unchanged.
"""
from __future__ import annotations
import argparse
from copy import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zipfile

LIMIT = 16  # per direction, maximum 32 clones per initialized race pool
V28 = '063733277ca3e2a37334fa2c1a9ebfaa310675d5d19a1ded2551b8cf803874d4'
V36 = '771cbb57bb7ee6ef2c19ce23151dd9584e2a0995f90bd43a084237b50638c4ce'
TRANSLATE = 133  # verified Lnam IDs in the hash-locked original movie
WORLD = 130
NOTES = """Redline Rumble v43 - Directional Reuse DIAGNOSTIC

GAMEPLAY UNVERIFIED. v39 remains the full-race-confirmed reference.
Extract to a NEW folder and use the included launcher. Keep v42 for comparison.

Each traffic direction retains up to 16 visual clones (32 total). After its
pool fills, the oldest clone moves to the next recycled car's world position.
It remains attached to that direction's moving parent. No additional model
allocation occurs after that direction reaches 16; no models are deleted.
This extends updates beyond the old cap, not unlimited simultaneous visibility.

DIAGNOSTIC LIMITATION: reused clones retain their initial body, materials,
rotation and scale. A rear visual can differ from the vehicle just passed.
The two pools fill independently; unused capacity is not shared.
Camera code, runtime files and original traffic instructions are preserved.

TEST v42 first, then v43 with the same race/car. Check rear visuals in both
directions well beyond the previous failure point, then finish, return to menu
and complete another race without restarting. Check B rear view in both C
camera modes, camera return, 4K/fullscreen, performance and normal collisions.
The green truck/checkered flag at victory are normal.
Report race/car, elapsed time, continuing rear traffic, appearance/position
problems, first/second-race outcomes and exact error text or crash log.
Static tests cannot establish Director lifetime safety or race cleanup.
Original-2003 difficulty equivalence remains unverified.
"""

def sha(data):
    return hashlib.sha256(data).hexdigest()

def emitter():
    path = Path(__file__).resolve().parents[1] / 'source/build_redline_v35.py'
    spec = importlib.util.spec_from_file_location('_v43_legacy', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    # This movie uses direct local indices, as independently audited for v42.
    m.loc = lambda b, n: b.emit(0x4c, n)
    m.setloc = lambda b, n: b.emit(0x52, n)
    m.create_one_visual = lambda b, direction: create_visual(m, b, direction)
    m.init_hook = lambda: initialize(m)
    return m

def pool(m, b, oncoming):
    m.prop(b, 438); m.push(b, 2 if oncoming else 1)
    m.argret(b, 2); m.call(b, 65)

def source(m, b, oncoming):
    (m.model_from_oncoming if oncoming else m.model_from_group_child)(b)

def initialize(m):
    b = m.Seq()
    for _ in range(2):
        m.argret(b, 0); b.emit(0x1e)
    m.argret(b, 2); b.emit(0x1e); m.setprop(b, 438)
    return b.resolved()

def create_visual(m, b, oncoming):
    m.push(b, LIMIT); pool(m, b, oncoming); m.getobj(b, 66)
    b.emit(0x0d); b.jmp(0x55, 'new_clone')
    pool(m, b, oncoming); m.push(b, 1); m.argret(b, 2); m.call(b, 65)
    m.setloc(b, 1)
    # receiver.translate(source.worldPosition - receiver.worldPosition,#world)
    m.loc(b, 1)
    source(m, b, oncoming); m.getobj(b, 105)
    m.loc(b, 1); m.getobj(b, 105); b.emit(0x06)
    m.sym(b, WORLD); m.args(b, 3); m.call(b, TRANSLATE)
    pool(m, b, oncoming); m.push(b, 1); m.args(b, 2); m.call(b, 432)
    pool(m, b, oncoming); m.loc(b, 1); m.args(b, 2); m.call(b, 78)
    b.jmp(0x53, 'done')
    b.label('new_clone')
    source(m, b, oncoming)
    # Names use original prefix and globally disjoint integers 1..16/17..32.
    m.cons(b, 11); m.cons(b, 14); b.emit(0x0a)
    pool(m, b, oncoming); m.getobj(b, 66)
    m.push(b, 17 if oncoming else 1); b.emit(0x05); b.emit(0x0a)
    m.argret(b, 2); m.call(b, 153); m.setloc(b, 1)
    m.prop(b, 402 if oncoming else 401); m.loc(b, 1); m.sym(b, 436)
    m.args(b, 3); m.call(b, 316)
    pool(m, b, oncoming); m.loc(b, 1); m.args(b, 2); m.call(b, 78)
    b.label('done')

def stack_peak(m, code, entry=0):
    """Validate every hook path; marker/call arity, joins, locals and stack."""
    instructions = {i['s']: i for i in m.decode(code, allow_end=True)}
    todo, seen, peak = [(0, 0, None)], {}, entry
    while todo:
        pc, depth, marker = todo.pop()
        if pc in seen:
            if seen[pc] != (depth, marker):
                raise ValueError('Inconsistent stack at merge')
            continue
        seen[pc] = depth, marker
        if pc == len(code):
            if depth or marker is not None:
                raise ValueError('Unbalanced hook exit')
            continue
        i = instructions[pc]; op, val = i['op'], i['val']
        if marker is not None and op not in (0x67, 0x1e):
            raise ValueError('Call marker not immediately consumed')
        if op in (0x4c, 0x52) and val not in (0, 1, 2):
            raise ValueError('Undeclared local')
        if op == 0x52 and val == 0:
            raise ValueError('Original traffic index overwritten')
        pops = pushes = 0
        if op in (0x41, 0x44, 0x45, 0x4a, 0x4c):
            pushes = 1
        elif op in (0x42, 0x43):
            marker = (val, op == 0x43); pushes = 1
        elif op in (0x05, 0x06, 0x0a, 0x0d):
            pops, pushes = 2, 1
        elif op in (0x50, 0x52, 0x55):
            pops = 1
        elif op == 0x61:
            pops, pushes = 1, 1
        elif op in (0x67, 0x1e):
            if marker is None or (op == 0x1e and not marker[1]):
                raise ValueError('Missing/invalid argument marker')
            pops, pushes = marker[0]+1, int(marker[1]); marker = None
        elif op not in (0x53, 0x54):
            raise ValueError(f'Unsupported opcode {op:#x}')
        if depth < pops:
            raise ValueError('Hook consumes caller stack')
        depth += pushes-pops; peak = max(peak, entry+depth)
        successors = ([i['target']] if op in (0x53, 0x54) else
                      [i['target'], i['e']] if op == 0x55 else [i['e']])
        todo.extend((p, depth, marker) for p in successors)
    return peak

def verify_original(m, original, changed, report):
    """Compare every original instruction and branch target after insertion."""
    for index, key in enumerate(('init_handler', 'race_handler')):
        old_size, old_at = struct.unpack_from('>II', original, 162+index*46)
        new_size, new_at = struct.unpack_from('>II', changed, 162+index*46)
        old = m.decode(original[old_at:old_at+old_size])
        new = m.decode(changed[new_at:new_at+new_size])
        inserts = report[key]['insertions']
        kept = [i for i in new if not any(p['new_byte_offset'] <= i['s'] <
                p['new_byte_offset']+p['inserted_bytes'] for p in inserts)]
        assert len(old) == len(kept)
        positions = {a['s']: b['s'] for a, b in zip(old, kept)}
        for a, b in zip(old, kept):
            assert (a['op'], a['w']) == (b['op'], b['w'])
            if a['target'] is None:
                assert a['raw'] == b['raw']
            else:
                assert b['target'] == positions[a['target']]

def build(v28, v36):
    if sha(v28) != V28 or sha(v36) != V36:
        raise ValueError('Wrong v28/v36 movie hash')
    m = emitter()
    original = m.resource(v28, 1509)
    changed, legacy_report = m.rewrite(original)
    verify_original(m, original, changed, legacy_report)
    # The v42 liveness checker independently walks original code after hooks.
    from build_rr_v42 import dead_until_written
    size, start = struct.unpack_from('>II', changed, 208)
    code = changed[start:start+size]
    assert struct.unpack_from('>H', changed, 222)[0] == 3
    assert struct.unpack_from('>I', changed, 246)[0] == 7
    peaks, live = [], {}
    for p in legacy_report['race_handler']['insertions']:
        at, length = p['new_byte_offset'], p['inserted_bytes']
        peaks.append(stack_peak(m, code[at:at+length], entry=1))
        for slot in (1, 2):
            live[f'{at+length:#x}:local{slot}'] = dead_until_written(code, at+length, slot)
    assert max(peaks) <= 7
    assert stack_peak(m, initialize(m)) <= 18
    game = bytearray(v36); offset = len(game)
    game.extend(b'rcsL'+struct.pack('<I', len(changed))+changed)
    rec = m.MAP+1509*m.REC_SZ
    struct.pack_into('<II', game, rec+4, len(changed), offset)
    struct.pack_into('<I', game, 4, len(game)-8)
    game = bytes(game)
    assert m.resource(game, 1509) == changed
    assert game[:4] == v36[:4] and game[8:rec+4] == v36[8:rec+4]
    assert game[rec+12:len(v36)] == v36[rec+12:]
    return game, {
        'status': 'STATIC VALIDATION PASSED; DIRECTOR GAMEPLAY PENDING',
        'source_v28_sha256': sha(v28), 'source_v36_sha256': sha(v36),
        'output_game_sha256': sha(game), 'changed_resource_ids': [1509],
        'unchanged_resource_count': 1599, 'camera_1506_unchanged': True,
        'original_instructions_and_branch_targets_preserved': True,
        'insertions': {k: legacy_report[k] for k in ('init_handler', 'race_handler')},
        'declared_locals': 3, 'local_operands': [0, 1, 2],
        'declared_stack_height': 7, 'hook_entry_depth': 1,
        'hook_absolute_stack_peaks': peaks, 'scratch_liveness': live,
        'visual_clone_limit_per_direction': LIMIT, 'visual_clone_limit_total': 32,
        'continuous_reuse': True, 'reuse': 'world-space delta translation',
        'reuse_model_setters': [], 'model_deletion': False,
        'reparent_on_reuse': False, 'appearance_rotation_scale_retained': True,
        'gameplay_tested': False, 'native_lifetime_safety_verified': False,
        'repeated_race_cleanup_verified': False,
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--v28', required=True, type=Path)
    p.add_argument('--v36', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    if not __debug__:
        p.error('Assertions must be enabled; do not use -O')
    if a.out.exists() or a.out.resolve() in (a.v28.resolve(), a.v36.resolve()):
        p.error('Choose a new output path; preserve existing archives')
    with zipfile.ZipFile(a.v28) as old, zipfile.ZipFile(a.v36) as base:
        for archive in (old, base):
            assert archive.testzip() is None
            assert len(archive.namelist()) == len(set(archive.namelist()))
        game, report = build(old.read('game.dir'), base.read('game.dir'))
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(a.out, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as dst:
            for entry in base.infolist():
                if entry.filename != 'README v36.txt':
                    dst.writestr(copy(entry), game if entry.filename == 'game.dir' else base.read(entry.filename))
            info = zipfile.ZipInfo('README v43.txt', (2026, 11, 5, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(info, NOTES.encode('utf-8'))
        with zipfile.ZipFile(a.out) as check:
            assert check.testzip() is None and check.read('game.dir') == game
            assert set(check.namelist()) == (set(base.namelist())-{'README v36.txt'}) | {'README v43.txt'}
            for name in set(base.namelist())-{'game.dir', 'README v36.txt'}:
                assert check.read(name) == base.read(name), name
    report['output_zip_sha256'] = sha(a.out.read_bytes())
    report['other_packaged_files_unchanged'] = True
    a.out.with_suffix('.validation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
