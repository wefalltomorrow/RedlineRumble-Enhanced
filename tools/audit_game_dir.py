#!/usr/bin/env python3
"""Compare two Redline Rumble game.dir files or ZIP builds without running them.

Reports logical Director resource changes, validates changed Lingo handlers,
and checks whether executable/runtime files differ. Requires Python 3.10+.

Usage:
  python tools/audit_game_dir.py RR_v36.zip RR_v37.zip --output audit.json

This is static validation only, never a guarantee of Windows stability.
"""
import argparse
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

MAP_OFFSET = 136
MAP_COUNT = 1600
MAP_RECORD_SIZE = 20
FREE_TAGS = {b'eerf', b'knuj'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    path = Path(path)
    if path.is_dir():
        return (path / 'game.dir').read_bytes(), {}
    if path.suffix.lower() != '.zip':
        return path.read_bytes(), {}
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError('ZIP CRC error in ' + bad)
        files = {}
        for name in archive.namelist():
            if name.endswith('/'):
                continue
            if name in files:
                raise ValueError('Duplicate archive entry: ' + name)
            files[name] = archive.read(name)
    if 'game.dir' not in files:
        raise ValueError('Archive does not contain game.dir')
    return files.pop('game.dir'), files


def resources(movie):
    if movie[:4] != b'XFIR':
        raise ValueError('Not an XFIR Director movie')
    if struct.unpack_from('<I', movie, 4)[0] + 8 != len(movie):
        raise ValueError('Director movie length mismatch')
    if len(movie) < MAP_OFFSET + MAP_COUNT * MAP_RECORD_SIZE:
        raise ValueError('Resource map truncated')
    found = []
    for index in range(MAP_COUNT):
        tag, length, offset, u0, u1 = struct.unpack_from(
            '<4sIIII', movie, MAP_OFFSET + MAP_RECORD_SIZE * index)
        if tag in FREE_TAGS:
            # Free-list metadata is allowed to contain nonzero pointers.
            found.append((tag, None))
            continue
        if (u0, u1) != (0, 0):
            raise ValueError('Unexpected live resource metadata: ' + str(index))
        if offset + 8 + length > len(movie):
            raise ValueError('Resource extends beyond movie: ' + str(index))
        if movie[offset:offset+8] != tag + struct.pack('<I', length):
            raise ValueError('Resource chunk header mismatch: ' + str(index))
        found.append((tag, movie[offset+8:offset+8+length]))
    return found


def decode(code):
    starts, branches = set(), []
    pos = 0
    while pos < len(code):
        start = pos
        starts.add(start)
        op = code[pos]
        pos += 1
        base = op if op < 0x40 else 0x40 + op % 0x40
        width = 0 if op < 0x40 else 4 if op >= 0xc0 else 2 if op >= 0x80 else 1
        if pos + width > len(code):
            raise ValueError('Truncated Lingo operand at ' + hex(start))
        arg = int.from_bytes(code[pos:pos+width], 'big') if width else None
        pos += width
        if base in (0x53, 0x54, 0x55):
            if arg is None:
                raise ValueError('Missing Lingo jump operand')
            branches.append((start, start - arg if base == 0x54 else start + arg))
    for at, target in branches:
        if target not in starts and target != len(code):
            raise ValueError('Invalid Lingo jump ' + hex(at) + ' -> ' + hex(target))
    return {'instruction_count': len(starts), 'branch_count': len(branches)}


def inspect_script(body):
    if body is None or len(body) < 92:
        raise ValueError('Truncated script resource')
    count, offset = struct.unpack_from('>HI', body, 72)
    if count > 10000 or offset + count * 46 > len(body):
        raise ValueError('Bad Lingo handler metadata')
    handlers = []
    for index in range(count):
        rec = offset + index * 46
        size, start = struct.unpack_from('>II', body, rec + 4)
        if start + size > len(body):
            raise ValueError('Lingo code exceeds script')
        code = body[start:start+size]
        handlers.append({'index': index, 'length': size,
                         'sha256': digest(code), **decode(code)})
    return handlers


def compare(reference, candidate):
    old_movie, old_files = load(reference)
    new_movie, new_files = load(candidate)
    old, new = resources(old_movie), resources(new_movie)
    changes = []
    for index, ((old_tag, old_body), (new_tag, new_body)) in enumerate(zip(old, new)):
        if (old_tag, old_body) == (new_tag, new_body):
            continue
        detail = {'id': index, 'from_type': old_tag[::-1].decode('latin-1'),
                  'to_type': new_tag[::-1].decode('latin-1'),
                  'old_length': len(old_body) if old_body is not None else None,
                  'new_length': len(new_body) if new_body is not None else None,
                  'old_sha256': digest(old_body) if old_body is not None else None,
                  'new_sha256': digest(new_body) if new_body is not None else None}
        if old_tag == new_tag == b'rcsL':
            detail['old_handlers'] = inspect_script(old_body)
            detail['new_handlers'] = inspect_script(new_body)
        changes.append(detail)
    old_names, new_names = set(old_files), set(new_files)
    runtime = {}
    for name in ('Projector.exe', 'Iml32.dll', 'Dirapi.dll'):
        runtime[name] = {'sha256_before': digest(old_files[name]) if name in old_files else None,
                         'sha256_after': digest(new_files[name]) if name in new_files else None,
                         'identical': old_files.get(name) == new_files.get(name)}
    return {'reference': str(reference), 'candidate': str(candidate),
            'game_sha256_before': digest(old_movie),
            'game_sha256_after': digest(new_movie),
            'changed_resource_ids': [r['id'] for r in changes],
            'unchanged_resource_count': MAP_COUNT - len(changes),
            'resource_changes': changes,
            'other_files': {
                'added': sorted(new_names - old_names),
                'removed': sorted(old_names - new_names),
                'modified': sorted(x for x in old_names & new_names
                                   if old_files[x] != new_files[x])},
            'runtime': runtime,
            'warning': 'Static verification only; cannot establish gameplay stability'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', type=Path)
    options = parser.parse_args()
    try:
        report = compare(options.reference, options.candidate)
    except (ValueError, OSError, struct.error, zipfile.BadZipFile) as error:
        parser.exit(1, 'Audit failed: ' + str(error) + '\n')
    output = json.dumps(report, indent=2) + '\n'
    if options.output:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(output, encoding='utf-8')
        print('Report:', options.output)
    else:
        print(output)
    print('Changed resource IDs:', report['changed_resource_ids'])


if __name__ == '__main__':
    main()
