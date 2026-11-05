#!/usr/bin/env python3
"""Install verified v42/v43 diagnostics from user-owned archives.

Standard library only. Never launches the game, overwrites a destination,
or changes the shared Director save. Run from the extracted source-only kit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

class InstallError(ValueError):
    pass

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise InstallError(f'Cannot read JSON: {path.name}: {exc}') from exc

def safe_name(name):
    """One canonical, relative Windows-safe file path; no aliases or streams."""
    if not isinstance(name, str) or not name or '\\' in name:
        raise InstallError(f'Invalid archive path: {name!r}')
    parts = name.split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{p}{n}' for p in ('COM', 'LPT') for n in range(1, 10)}
    for part in parts:
        if (part in ('', '.', '..') or part.endswith((' ', '.')) or
            any(ord(c) < 32 or c in '<>:"|?*' for c in part) or
            part.split('.')[0].upper() in reserved):
            raise InstallError(f'Unsafe archive path: {name!r}')
    return PurePosixPath(name)

def inventory(archive):
    names, folded = {}, set()
    for info in archive.infolist():
        safe_name(info.filename)
        key = info.filename.casefold()
        if key in folded or info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
            raise InstallError(f'Duplicate, directory or link entry: {info.filename}')
        if info.flag_bits & 1:
            raise InstallError('Encrypted archive entries are not supported')
        names[info.filename] = info; folded.add(key)
    # Reject file/directory collisions even on case-insensitive Windows.
    for name in names:
        parts = name.casefold().split('/')
        if any('/'.join(parts[:n]) in folded for n in range(1, len(parts))):
            raise InstallError(f'File/directory collision: {name}')
    return names

def verify_archive(path, expected):
    """Check every file, including DLLs/launchers, before invoking builders."""
    with zipfile.ZipFile(path) as z:
        entries = inventory(z)
        if set(entries) != set(expected):
            raise InstallError(f'{path.name}: file list differs from the recovered baseline')
        for name, record in expected.items():
            if entries[name].file_size != record['size']:
                raise InstallError(f'{path.name}: wrong size for {name}')
            if sha(z.read(name)) != record['sha256']:
                raise InstallError(f'{path.name}: hash mismatch for {name}')
    return sha(path.read_bytes())

def checked_file(root, name):
    safe_name(name)
    path = root.joinpath(*name.split('/'))
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)():
            raise InstallError(f'Symlink in tracked file path: {name}')
    if not path.resolve().is_relative_to(root.resolve()):
        raise InstallError(f'File escapes root: {name}')
    return path

def verify_files(root, expected):
    failures = []
    for name, record in expected.items():
        path = checked_file(root, name)
        if not path.is_file(): failures.append(f'missing: {name}')
        elif path.stat().st_size != record['size'] or sha(path.read_bytes()) != record['sha256']:
            failures.append(f'changed: {name}')
    if failures:
        raise InstallError('Files differ from the recorded manifest:\n'+'\n'.join(failures))

def file_records(root):
    records = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
            raise InstallError('Unexpected symlink in generated output')
        if path.is_file():
            data = path.read_bytes()
            records[path.relative_to(root).as_posix()] = {'size': len(data), 'sha256': sha(data)}
    return records

def verify_kit(root):
    manifest = read_json(root/'KIT_MANIFEST.json')
    if manifest.get('format') != 'redline-source-kit-v1':
        raise InstallError('Unsupported source kit format')
    verify_files(root, manifest['files'])
    if set(file_records(root)) != set(manifest['files']) | {'KIT_MANIFEST.json'}:
        raise InstallError('Source kit contains unexpected files; extract a fresh kit')
    return manifest

def extract_verified(archive_path, destination):
    """Extract only regular files to a new staging directory, never zip.extract."""
    destination.mkdir()
    with zipfile.ZipFile(archive_path) as z:
        for name in inventory(z):
            path = destination.joinpath(*name.split('/'))
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as out:
                out.write(z.read(name))

def build_one(kit, version, inputs, output):
    needed = ('v39',) if version == 'v42' else ('v28', 'v36')
    command = [sys.executable, '-E', '-s', '-B', str(kit/'experiments'/f'build_rr_{version}.py')]
    for key in needed:
        command.extend(('--'+key, str(inputs[key])))
    command.extend(('--out', str(output)))
    result = subprocess.run(command, cwd=kit, capture_output=True, text=True)
    if result.returncode:
        raise InstallError(f'{version} builder failed:\n{result.stdout}\n{result.stderr}')

TEST_GUIDE = """Redline Rumble diagnostic comparison

Both v42 and v43 remain gameplay-unverified. v39 is the full-race reference.
Open the selected version folder and use its existing .cmd launcher.

Test v42 first, then v43 with the same race and car. Check rear traffic in
both directions after pool saturation, B rear view in both C camera modes,
normal collisions, finish/victory/menu, then another race without restarting.
Record race/car, elapsed time, first/second race outcome and any exact error.
v43 retains clone appearance/orientation and can show mismatches or FIFO pops.
The green truck/checkered flag at victory are normal.

Folders are separate but Director uses a shared profile/save location. This
installer does not modify or isolate saves. No game has been launched by it.

To check files later: python install.py --verify "PATH TO THIS FOLDER"
Changed files mean changed since installation; saves/logs can change during
normal play. The report is not a diagnosis of game corruption or a crash.

v42 race/car:
v42 first race / second race:
v43 race/car:
v43 first race / second race:
Rear traffic / camera / performance observations:
Exact error and elapsed time:
"""

def install(kit, selection, inputs, destination, progress=print):
    kit, destination = kit.resolve(), destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise InstallError('Destination already exists; choose a NEW folder')
    manifest = verify_kit(kit)
    profiles = read_json(kit/'profiles.json')
    if profiles.get('format') != 'redline-input-profiles-v1':
        raise InstallError('Unsupported input profile format')
    versions = ['v42', 'v43'] if selection == 'comparison' else [selection]
    needed = sorted({key for v in versions for key in profiles['builds'][v]['inputs']})
    archive_hashes = {}
    for key in needed:
        if key not in inputs or inputs[key] is None:
            raise InstallError(f'Missing --{key} archive')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.rr-kit-', dir=destination.parent) as temp:
        work = Path(temp); ready = work/'ready'; ready.mkdir()
        # Builders read private, verified snapshots, so later changes to the
        # supplied archives cannot change the runtime being installed.
        snapshots = {}
        for key in needed:
            progress(f'Checking every file in {key}...')
            snapshots[key] = work/f'input-{key}.zip'
            shutil.copyfile(inputs[key], snapshots[key])
            archive_hashes[key] = verify_archive(snapshots[key], profiles['inputs'][key]['files'])
        builds = {}
        for version in versions:
            progress(f'Building and checking {version}...')
            archive_path = work/f'{version}.zip'
            build_one(kit, version, snapshots, archive_path)
            verify_archive(archive_path, profiles['builds'][version]['files'])
            with zipfile.ZipFile(archive_path) as z:
                actual = sha(z.read('game.dir'))
            if actual != profiles['builds'][version]['game_sha256']:
                raise InstallError(f'{version}: unexpected output movie hash')
            extract_verified(archive_path, ready/version)
            report = archive_path.with_suffix('.validation.json')
            shutil.copyfile(report, ready/f'{version}.validation.json')
            builds[version] = {'game_sha256': actual, 'archive_sha256': sha(archive_path.read_bytes())}
        (ready/'TEST_RESULTS.txt').write_text(TEST_GUIDE, encoding='utf-8')
        tracked = file_records(ready)
        del tracked['TEST_RESULTS.txt']  # User-editable observations, not runtime.
        record = {'format': 'redline-installation-v1', 'source_commit': manifest['source_commit'],
                  'kit_manifest_sha256': sha((kit/'KIT_MANIFEST.json').read_bytes()),
                  'input_archive_sha256': archive_hashes, 'builds': builds,
                  'files': tracked, 'editable_files': ['TEST_RESULTS.txt'], 'gameplay_tested': False}
        verify_files(ready, record['files'])
        # Reserve exclusively only after all validation. Never overwrite even
        # if another process created the destination while builders ran.
        destination.mkdir()
        incomplete = destination/'INSTALLATION_INCOMPLETE.txt'
        incomplete.write_text('Publication interrupted. Do not use as a verified installation.\n', encoding='utf-8')
        for item in ready.iterdir():
            shutil.move(str(item), str(destination/item.name))
        verify_files(destination, record['files'])
        (destination/'INSTALLATION.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
        incomplete.unlink()
    progress(f'Installed verified files into {destination}')
    return record

def verify_installation(root):
    if (root/'INSTALLATION_INCOMPLETE.txt').exists():
        raise InstallError('Installation is marked incomplete')
    record = read_json(root/'INSTALLATION.json')
    if record.get('format') != 'redline-installation-v1':
        raise InstallError('Unsupported installation manifest')
    verify_files(root, record['files'])
    actual = set(file_records(root)) - {'INSTALLATION.json'}
    extras = sorted(actual-set(record['files'])-set(record.get('editable_files', [])))
    return {'tracked_files_verified': len(record['files']), 'untracked_files': extras,
            'source_commit': record['source_commit'], 'gameplay_tested': False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', choices=('comparison', 'v42', 'v43'), default='comparison')
    for key in ('v28', 'v36', 'v39'): p.add_argument('--'+key, type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--verify', type=Path, help='Check an installed folder without building')
    a = p.parse_args()
    try:
        if a.verify:
            if a.out or any(getattr(a, k) for k in ('v28', 'v36', 'v39')):
                p.error('--verify cannot be combined with installation paths')
            print(json.dumps(verify_installation(a.verify), indent=2))
        else:
            if not a.out: p.error('--out NEW_FOLDER is required')
            install(Path(__file__).resolve().parent, a.build,
                    {k:getattr(a, k) for k in ('v28', 'v36', 'v39')}, a.out)
    except (InstallError, OSError, zipfile.BadZipFile, KeyError, TypeError) as exc:
        p.exit(1, f'Installation/check stopped: {exc}\n')

if __name__ == '__main__':
    main()
