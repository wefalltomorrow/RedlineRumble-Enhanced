#!/usr/bin/env python3
"""v42 diagnostic: fix eleven out-of-range local operands in exact v39.

Changes only 8->1 and 16->2 in injected exitFrame local accesses. Keeps
v39's cap/no-delete behavior, cameras, assets and runtime byte-identical.
Requires a user-owned v39 ZIP. No native gameplay safety claim is made.
"""
from __future__ import annotations
import argparse
from copy import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'source'))
import build_redline_v35 as legacy

V39 = '73b5bc4e2e57e35abc839eb1a1152d88cb7405be60ee9a7ab7b0748be5a375b5'
LOCAL_MAP = {8: 1, 16: 2}
EXPECTED_SITES = (0x582, 0x584, 0x5b4, 0x5cd, 0x5d2, 0x5df,
                  0x5e7, 0x5ea, 0xa80, 0xa85, 0xa92)
# Ranges reproduced by the historical v39 emitter; offsets in exitFrame.
HOOK_RANGES = ((0x580, 111), (0xa56, 66))
# Independent full-handler audit of the hash-locked v39 input found one
# live stack value at both entries. This is not inferred for arbitrary code.
HOOK_ENTRY_DEPTH = 1
NOTES = """Redline Rumble v42 - Local-index correction DIAGNOSTIC

GAMEPLAY NOT YET VERIFIED. v39 remains the full-race-confirmed reference.
Extract this ZIP to a NEW folder and use the existing launcher.

This diagnostic changes exactly eleven game.dir bytes relative to v39:
injected traffic scratch-local indices 8/16 become 1/2, matching the
original three-local handler and its bytecode format. All other game
bytes, cameras, assets and runtime files are unchanged.

This intentionally keeps v39's maximum of 32 rear visual clones and stops
adding them after the cap. It does NOT yet implement continuous reuse.
The out-of-range locals were found while auditing v41; we must test this
correction independently before adding another reuse mechanism. This
finding does not prove the cause of previous native crashes.

TEST: choose the race/car used for the v39 success and previous crashes.
Check that rear cars appear correctly, both traffic directions behave
normally, and B rear-view/C hood-chase switching and camera return work.
Drive through the full race, finish/victory and menu. Then run another
race without restarting. Check 4K/fullscreen, performance, collision and
difficulty behavior against v39. Green truck/checkered flag are normal.

Send race/car, approximate elapsed time, whether the first rear visuals
appear, and full-race/second-race results. Capture exact Director error
text or the Windows event/crash-capture log if it fails. A screenshot or
video is useful for incorrect traffic or camera behavior.

Original-2003 difficulty equivalence, repeated-race cleanup, native
stability and indefinite rear visibility remain unresolved.
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def correct_locals(code, declared=3):
    """Correct known legacy operands; reject other undeclared indices."""
    result = bytearray(code)
    fixes = []
    for ins in legacy.decode(code):
        if ins['op'] not in (0x4c, 0x52):
            continue
        old = ins['val']
        if old in LOCAL_MAP:
            new = LOCAL_MAP[old]
            if new >= declared:
                raise ValueError('Corrected local is outside the declaration')
            result[ins['s']+1:ins['e']] = new.to_bytes(ins['w'], 'big')
            fixes.append({'instruction_offset': ins['s'], 'from': old, 'to': new})
        elif old >= declared:
            raise ValueError('Unexpected undeclared local operand: ' + str(old))
    return bytes(result), fixes


def dead_until_written(code, start, slot):
    """CFG proof: every reachable read after start has a prior slot write.

    Stops a path at its first write or handler return. Covers conditional
    and backward branches, rather than relying on linear access order.
    """
    ins = {i['s']: i for i in legacy.decode(code)}
    todo, seen = [start], set()
    while todo:
        pc = todo.pop()
        if pc in seen or pc == len(code):
            continue
        seen.add(pc)
        item = ins[pc]
        if item['op'] == 0x4c and item['val'] == slot:
            raise ValueError(f'Local {slot} is live at {pc:#x}')
        if item['op'] == 0x01 or (item['op'] == 0x52 and item['val'] == slot):
            continue
        if item['op'] in (0x53, 0x54):
            todo.append(item['target'])
        elif item['op'] == 0x55:
            todo.extend((item['target'], item['e']))
        else:
            todo.append(item['e'])
    return len(seen)


def hook_stack_bound(code, entry_depth=0):
    """Return absolute peak, preserving the caller's stack on every path.

    Only the emitted hook subset is supported. Argument markers are tracked
    in the path state so a jump cannot bypass the marker before a call.
    Entry depth is supplied by the independent hash-locked handler audit.
    """
    if not isinstance(entry_depth, int) or entry_depth < 0:
        raise ValueError('Invalid hook entry depth')
    decoded = legacy.decode(code, allow_end=True)
    ins = {i['s']: i for i in decoded}
    todo, seen, peak = [(0, (), None)], {}, entry_depth
    while todo:
        pc, stack, marker = todo.pop()
        if pc in seen:
            if seen[pc] != (stack, marker):
                raise ValueError('Stack state differs at branch merge')
            continue
        seen[pc] = (stack, marker)
        if pc == len(code):
            if stack or marker is not None:
                raise ValueError('Hook exits with a nonempty stack')
            continue
        i = ins[pc]
        op = i['op']
        if marker is not None and op != 0x67:
            raise ValueError('Argument marker must be followed by a call')
        pops, pushes = 0, 0
        if op in (0x41, 0x44, 0x45, 0x4a, 0x4c):
            pushes = 1
        elif op in (0x42, 0x43):
            marker = (i['val'], op == 0x43)
            pushes = 1
        elif op in (0x05, 0x0a, 0x0d):
            pops, pushes = 2, 1
        elif op in (0x52, 0x55):
            pops = 1
        elif op == 0x61:
            pops, pushes = 1, 1
        elif op == 0x67:
            if marker is None:
                raise ValueError('Call lacks an immediate argument marker')
            pops, pushes = marker[0] + 1, int(marker[1])
            marker = None
        elif op not in (0x53, 0x54):
            raise ValueError(f'Unmodeled hook opcode {op:#x}')
        if len(stack) < pops:
            raise ValueError('Hook stack underflow')
        stack = stack[:len(stack)-pops] + (None,) * pushes
        peak = max(peak, entry_depth + len(stack))
        if op in (0x53, 0x54):
            todo.append((i['target'], stack, marker))
        elif op == 0x55:
            todo.extend(((i['target'], stack, marker), (i['e'], stack, marker)))
        else:
            todo.append((i['e'], stack, marker))
    return peak


def build(movie):
    if sha(movie) != V39:
        raise ValueError('Wrong v39 game.dir SHA-256; refusing to patch')
    script = legacy.resource(movie, 1509)
    count, handlers = struct.unpack_from('>HI', script, 72)
    assert (count, handlers) == (2, 158)
    record = handlers + 46
    size, start = struct.unpack_from('>II', script, record+4)
    declared = struct.unpack_from('>H', script, record+18)[0]
    stack_limit = struct.unpack_from('>I', script, record+42)[0]
    assert declared == 3 and stack_limit == 7
    code = script[start:start+size]
    corrected, fixes = correct_locals(code, declared)
    assert tuple(f['instruction_offset'] for f in fixes) == EXPECTED_SITES
    assert len(corrected) == len(code)
    assert all(any(a <= f['instruction_offset'] < a+n for a, n in HOOK_RANGES) for f in fixes)
    liveness = {}
    peaks = []
    for a, n in HOOK_RANGES:
        peaks.append(hook_stack_bound(corrected[a:a+n], HOOK_ENTRY_DEPTH))
        preceding = next(i for i in legacy.decode(code) if i['e'] == a)
        assert preceding['op'] == 0x55
        for slot in ((1, 2) if a == HOOK_RANGES[0][0] else (1,)):
            liveness[f'{a+n:#x}:local{slot}'] = dead_until_written(corrected, a+n, slot)
    assert max(peaks) <= stack_limit
    old_ins, new_ins = legacy.decode(code), legacy.decode(corrected)
    for old, new in zip(old_ins, new_ins):
        assert (old['s'], old['e'], old['op'], old['target']) == (new['s'], new['e'], new['op'], new['target'])
        if old['s'] not in EXPECTED_SITES:
            assert old['raw'] == new['raw']
    resource_at = struct.unpack_from('<I', movie, legacy.MAP + 1509*legacy.REC_SZ + 8)[0]+8
    absolute = resource_at+start
    output = bytearray(movie)
    output[absolute:absolute+size] = corrected
    output = bytes(output)
    changed = [i for i, (a, b) in enumerate(zip(movie, output)) if a != b]
    assert changed == [absolute+s+1 for s in EXPECTED_SITES]
    assert len(output) == len(movie) and len(changed) == 11
    assert legacy.resource(output, 1506) == legacy.resource(movie, 1506)
    report = {
        'status': 'STATIC VALIDATION PASSED; DIRECTOR GAMEPLAY PENDING',
        'baseline_game_sha256': sha(movie), 'output_game_sha256': sha(output),
        'changed_resource_ids': [1509], 'unchanged_resource_count': 1599,
        'changed_byte_count': len(changed), 'changed_file_offsets': changed,
        'local_fixes': fixes, 'declared_exitFrame_locals': declared,
        'declared_stack_height': stack_limit,
        'injected_hook_stack_entry_depth': HOOK_ENTRY_DEPTH,
        'injected_hook_stack_peaks_above_entry': [p-HOOK_ENTRY_DEPTH for p in peaks],
        'injected_hook_stack_absolute_peaks': peaks,
        'scratch_liveness_visited_instructions': liveness,
        'all_nonlocal_instructions_and_branches_unchanged': True,
        'camera_1506_unchanged': True, 'visual_clone_limit': 32,
        'continuous_reuse': False, 'new_model_deletion': False,
        'gameplay_tested': False, 'native_crash_cause_proven': False,
        'original_2003_difficulty_equivalence_verified': False,
    }
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v39', required=True, type=Path)
    parser.add_argument('--out', type=Path, default=Path('RR_v42_LocalIndices_Diagnostic.zip'))
    args = parser.parse_args()
    if not __debug__:
        parser.error('Run without -O; validation assertions must be enabled')
    if args.out.exists() or args.out.resolve() == args.v39.resolve():
        parser.error('Choose a new output path; existing builds are preserved')
    with zipfile.ZipFile(args.v39) as base:
        assert base.testzip() is None
        assert len(base.namelist()) == len(set(base.namelist()))
        game, report = build(base.read('game.dir'))
        # Archived v39 accidentally named its current notes README v38.txt.
        old_notes = {'README v38.txt', 'README v39.txt'} & set(base.namelist())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.out, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as dst:
            for entry in base.infolist():
                if entry.filename not in old_notes:
                    dst.writestr(copy(entry), game if entry.filename == 'game.dir' else base.read(entry.filename))
            info = zipfile.ZipInfo('README v42.txt', (2026, 10, 25, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(info, NOTES.encode('utf-8'))
        with zipfile.ZipFile(args.out) as check:
            assert check.testzip() is None and check.read('game.dir') == game
            assert set(check.namelist()) == (set(base.namelist())-old_notes) | {'README v42.txt'}
            for name in set(base.namelist()) - {'game.dir'} - old_notes:
                assert check.read(name) == base.read(name), name
    report['output_zip_sha256'] = sha(args.out.read_bytes())
    report['other_packaged_files_unchanged'] = True
    path = args.out.with_suffix('.validation.json')
    path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
