#!/usr/bin/env python3
"""Build a Redline Rumble v36 camera / original v28 traffic A/B diagnostic.

Use verified, user-owned original development ZIP files. Nothing is downloaded;
no game binaries are checked into source control. The resulting game ZIP may
be redistributed only as permitted by the underlying owners' rights.

The output retains the v36 camera script #1506 and all v36 runtime/configuration
files, but restores v28 traffic script #1509 (no visual-only rear ghost clones).
This is a troubleshooting build, NOT a finished release or crash fix.
"""
from __future__ import annotations
import argparse
from copy import copy
import hashlib
import json
import struct
import zipfile
from pathlib import Path

V28_SHA = '063733277ca3e2a37334fa2c1a9ebfaa310675d5d19a1ded2551b8cf803874d4'
V36_SHA = '771cbb57bb7ee6ef2c19ce23151dd9584e2a0995f90bd43a084237b50638c4ce'
COUNT = 1600
MAP_START = 136
RECORD_SIZE = 20
CAMERA_RESOURCE = 1506
TRAFFIC_RESOURCE = 1509


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resource(movie: bytes, index: int) -> bytes | None:
    if not 0 <= index < COUNT:
        raise ValueError(f'Invalid Director resource index: {index}')
    rec_pos = MAP_START + RECORD_SIZE * index
    if rec_pos + RECORD_SIZE > len(movie):
        raise ValueError(f'Resource table truncated at {index}')
    tag, size, off, aux1, aux2 = struct.unpack_from('<4sIIII', movie, rec_pos)
    if size == 0:
        return None  # Director free/junk/tombstone entry, no active payload
    if aux1 or aux2 or not size or off + size + 8 > len(movie):
        raise ValueError(f'Invalid resource metadata at {index}')
    if movie[off:off + 8] != tag + struct.pack('<I', size):
        raise ValueError(f'Resource header mismatch at {index}')
    return movie[off + 8: off + 8 + size]


def build(v28: bytes, v36: bytes) -> tuple[bytes, dict]:
    if sha(v28) != V28_SHA:
        raise ValueError('v28 game.dir hash does not match known source version')
    if sha(v36) != V36_SHA:
        raise ValueError('v36 game.dir hash does not match known source version')
    if v28[:4] != v36[:4]:
        raise ValueError('Director movie magic changed unexpectedly')

    changed_between_v28_v36 = [i for i in range(COUNT) if resource(v28, i) != resource(v36, i)]
    if changed_between_v28_v36 != [CAMERA_RESOURCE, TRAFFIC_RESOURCE]:
        raise ValueError(f'Unexpected v28 to v36 script differences: {changed_between_v28_v36}')

    camera = resource(v36, CAMERA_RESOURCE)
    base_traffic = resource(v28, TRAFFIC_RESOURCE)
    new_movie = bytearray(v28)
    append_pos = len(new_movie)
    new_movie.extend(b'rcsL' + struct.pack('<I', len(camera)) + camera)
    rec_pos = MAP_START + CAMERA_RESOURCE * RECORD_SIZE
    if new_movie[rec_pos:rec_pos + 4] != b'rcsL':
        raise ValueError('Camera resource record tag unexpectedly changed')
    struct.pack_into('<II', new_movie, rec_pos + 4, len(camera), append_pos)
    struct.pack_into('<I', new_movie, 4, len(new_movie) - 8)
    output = bytes(new_movie)

    if resource(output, CAMERA_RESOURCE) != camera:
        raise AssertionError('v36 camera not retained')
    if resource(output, TRAFFIC_RESOURCE) != base_traffic:
        raise AssertionError('v28 traffic not restored')
    delta_v36 = [i for i in range(COUNT) if resource(output, i) != resource(v36, i)]
    delta_v28 = [i for i in range(COUNT) if resource(output, i) != resource(v28, i)]
    if delta_v36 != [TRAFFIC_RESOURCE] or delta_v28 != [CAMERA_RESOURCE]:
        raise AssertionError((delta_v36, delta_v28))
    for i in range(COUNT):
        if i == CAMERA_RESOURCE:
            continue
        p = MAP_START + i * RECORD_SIZE
        if output[p:p + RECORD_SIZE] != v28[p:p + RECORD_SIZE]:
            raise AssertionError(f'Unintended resource mapping changed: {i}')
    return output, {
        'build': 'v36 A/B without v35 rear visual clones',
        'validation': 'STATIC CHECKS PASSED, WINDOWS GAMEPLAY NOT TESTED',
        'source_game_v28_sha256': sha(v28),
        'source_game_v36_sha256': sha(v36),
        'output_game_sha256': sha(output),
        'director_resources': COUNT,
        'changed_resources_relative_to_v36': delta_v36,
        'changed_resources_relative_to_v28': delta_v28,
        'camera_1506_sha256': sha(resource(output, CAMERA_RESOURCE)),
        'traffic_1509_sha256': sha(resource(output, TRAFFIC_RESOURCE)),
        'camera_same_as_v36': True,
        'traffic_same_as_v28': True,
        'other_1598_resource_payloads_unchanged': True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v28', type=Path, required=True, help='Known v28 CameraFix ZIP')
    parser.add_argument('--v36', type=Path, required=True, help='Known v36 RearCamera ZIP')
    parser.add_argument('--out', type=Path, default=Path('RR_v36_NoGhosts_AB.zip'))
    args = parser.parse_args()

    with zipfile.ZipFile(args.v28) as base, zipfile.ZipFile(args.v36) as latest:
        if base.testzip() or latest.testzip():
            raise ValueError('Input archive failed CRC validation')
        if set(base.namelist()) ^ set(latest.namelist()) != {'README v28.txt', 'README v36.txt'}:
            raise ValueError('Unexpected archive file list differences')
        v28_movie = base.read('game.dir')
        v36_movie = latest.read('game.dir')
        output, report = build(v28_movie, v36_movie)
        original_ini = latest.read('Projector.ini')
        notes = (
            'Redline Rumble — A/B Crash Isolation Build (v36 No Ghosts)\n\n'
            'This is a diagnostic comparison, not a stability fix.\n'
            'Same v36 hood/chase and rear-facing cameras.\n'
            'Original v28 traffic logic: no v35 rear visual clones.\n'
            'Road scale, traffic pools, race difficulty, engine DLLs remain unchanged.\n'
            'Cars disappearing behind you is EXPECTED in this diagnostic.\n\n'
            'Test the exact same car/opponent/race as the v36/v37 crashes.\n'
            'If this build completes when v36 crashes, investigate ghost-model accumulation.\n'
            'If it also crashes, investigate shared v28/v36 systems and original runtime.\n'
            'Capture the Windows Application event, crash dump and memory CSV.\n'
            'Keep all game versions in separate folders.\n'
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as out:
            for entry in latest.infolist():
                if entry.filename == 'README v36.txt':
                    continue
                data = output if entry.filename == 'game.dir' else latest.read(entry.filename)
                out.writestr(copy(entry), data)
            out.writestr('README A-B NoGhosts.txt', notes)
        with zipfile.ZipFile(args.out) as test:
            if test.testzip() is not None:
                raise AssertionError('Output ZIP CRC error')
            assert test.read('game.dir') == output
            assert test.read('Projector.ini') == original_ini
            expected = (set(latest.namelist()) - {'README v36.txt'}) | {'README A-B NoGhosts.txt'}
            assert set(test.namelist()) == expected
            for name in set(latest.namelist()) - {'game.dir', 'README v36.txt'}:
                if latest.read(name) != test.read(name):
                    raise AssertionError(f'Unexpected altered runtime file: {name}')
    report.update({
        'output_zip': str(args.out),
        'output_zip_sha256': sha(args.out.read_bytes()),
        'all_runtime_files_identical_to_v36': True,
        'projector_ini_identical_to_v36': True,
    })
    report_path = args.out.with_name(args.out.stem + '_audit.json')
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('Report:', report_path)


if __name__ == '__main__':
    main()
