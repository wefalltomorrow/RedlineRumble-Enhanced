#!/usr/bin/env python3
"""Package only allowlisted source from an explicit Git commit (no game files)."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

FILES = {
    'install.py': 'diagnostics/install.py',
    'profiles.json': 'diagnostics/profiles.json',
    'README.md': 'diagnostics/README.md',
    'experiments/build_rr_v42.py': 'experiments/build_rr_v42.py',
    'experiments/build_rr_v43.py': 'experiments/build_rr_v43.py',
    'source/build_redline_v35.py': 'source/build_redline_v35.py',
}

def package(repo, ref, output):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args])
    commit = git('rev-parse', '--verify', ref+'^{commit}').decode().strip()
    payload = {name: git('show', f'{commit}:{path}') for name, path in FILES.items()}
    manifest = {'format': 'redline-source-kit-v1', 'source_commit': commit,
                'files': {name: {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                          for name, data in payload.items()}}
    payload['KIT_MANIFEST.json'] = (json.dumps(manifest, indent=2, sort_keys=True)+'\n').encode()
    # STORE also avoids zlib-version differences between machines.
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED) as z:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 5, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    return {'source_commit': commit, 'sha256': hashlib.sha256(Path(output).read_bytes()).hexdigest(),
            'files': sorted(payload)}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ref', required=True, help='Committed source ref; dirty working files are ignored')
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--out', type=Path, required=True, help='New ZIP path; parent must exist')
    a = p.parse_args()
    print(json.dumps(package(a.repo, a.ref, a.out), indent=2))

if __name__ == '__main__':
    main()
