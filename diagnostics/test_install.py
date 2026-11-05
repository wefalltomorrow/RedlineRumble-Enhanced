"""Synthetic fixtures only: no game or runtime binaries needed."""
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

import install as m

def write_zip(path, entries):
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in entries:
            z.writestr(name, data)

def records(entries):
    return {n: {'size': len(d), 'sha256': m.sha(d)} for n, d in entries}

class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kit = self.root/'kit'; self.kit.mkdir()
        self.dest = self.root/'installed'
        self.entries = [('game.dir', b'original'), ('runtime.dll', b'runtime')]
        self.archive = self.root/'input.zip'; write_zip(self.archive, self.entries)
        self.inputs = {v: self.archive for v in ('v28', 'v36', 'v39')}
        profiles = {'format':'redline-input-profiles-v1',
                    'inputs':{v:{'files':records(self.entries)} for v in self.inputs},
                    'builds':{v:{'inputs':needed, 'game_sha256':m.sha(v.encode()),
                                 'files':records([('game.dir',v.encode()), ('runtime.dll',b'runtime')])}
                              for v,needed in [('v42',['v39']),('v43',['v28','v36'])]}}
        (self.kit/'profiles.json').write_text(json.dumps(profiles), encoding='utf-8')
        self.seal()

    def seal(self):
        files = m.file_records(self.kit); files.pop('KIT_MANIFEST.json', None)
        (self.kit/'KIT_MANIFEST.json').write_text(json.dumps({
            'format':'redline-source-kit-v1','source_commit':'fixture','files':files}), encoding='utf-8')

    def builder(self, kit, version, inputs, output):
        for key, path in inputs.items():
            self.assertNotEqual(path, self.archive)
            m.verify_archive(path, records(self.entries))
        write_zip(output, [('game.dir',version.encode()), ('runtime.dll',b'runtime')])
        output.with_suffix('.validation.json').write_text('{}', encoding='utf-8')

    def run_install(self, builder=None, selection='comparison'):
        with patch.object(m, 'build_one', side_effect=builder or self.builder):
            return m.install(self.kit, selection, dict(self.inputs), self.dest, lambda _:None)

    def test_success_comparison_and_editable_notes(self):
        result = self.run_install()
        self.assertEqual(set(result['builds']), {'v42','v43'})
        self.assertFalse(result['gameplay_tested'])
        (self.dest/'TEST_RESULTS.txt').write_text('my observations')
        self.assertEqual(m.verify_installation(self.dest)['untracked_files'], [])
        (self.dest/'new.log').write_text('extra')
        self.assertEqual(m.verify_installation(self.dest)['untracked_files'], ['new.log'])

    def test_single_build_needs_only_its_inputs(self):
        self.inputs = {'v39':self.archive}
        self.assertEqual(set(self.run_install(selection='v42')['builds']), {'v42'})

    def test_wrong_movie_runtime_size_missing_extra(self):
        for bad in [[('game.dir', b'altered!'), self.entries[1]],
                    [self.entries[0], ('runtime.dll', b'changed')],
                    [self.entries[0], ('runtime.dll', b'x')],
                    self.entries[:1], self.entries+[('extra',b'x')]]:
            with self.subTest(bad=bad):
                write_zip(self.archive, bad)
                with self.assertRaises(m.InstallError): self.run_install()
                self.assertFalse(self.dest.exists())

    def test_unsafe_and_alias_archive_entries(self):
        with self.assertRaises(m.InstallError): m.safe_name('a\\b')
        for name in ['../escape', '/absolute', 'C:/drive', 'a:stream',
                     'CON.txt', 'a.', 'a ', 'dir//a', 'dir/../a', 'dir/']:
            with self.subTest(name=name):
                write_zip(self.archive, [(name,b'x')])
                with zipfile.ZipFile(self.archive) as z:
                    with self.assertRaises(m.InstallError): m.inventory(z)
        for entries in [[('a',b''),('A',b'')], [('a',b''),('a/b',b'')], [('a',b''),('a',b'')]]:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                write_zip(self.archive, entries)
            with zipfile.ZipFile(self.archive) as z:
                with self.assertRaises(m.InstallError): m.inventory(z)

    def test_symlink_archive_entry(self):
        info = zipfile.ZipInfo('link'); info.create_system=3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        write_zip(self.archive, [(info,b'elsewhere')])
        with zipfile.ZipFile(self.archive) as z:
            with self.assertRaises(m.InstallError): m.inventory(z)

    def test_source_tamper_and_extra_import(self):
        (self.kit/'profiles.json').write_text('{}')
        with self.assertRaises(m.InstallError): self.run_install()
        self.seal()
        (self.kit/'hashlib.py').write_text('bad')
        with self.assertRaises(m.InstallError): m.verify_kit(self.kit)

    def test_existing_destination_untouched(self):
        self.dest.mkdir(); sentinel=self.dest/'saved'; sentinel.write_bytes(b'keep')
        with self.assertRaises(m.InstallError): self.run_install()
        self.assertEqual(sentinel.read_bytes(), b'keep')
        self.assertEqual(len(list(self.dest.iterdir())),1)

    def test_bad_builder_output_does_not_publish(self):
        def bad(kit, version, inputs, output):
            self.builder(kit, version, inputs, output)
            write_zip(output, [('game.dir', b'wrong')])
        with self.assertRaises(m.InstallError): self.run_install(bad)
        self.assertFalse(self.dest.exists())

    def test_input_change_during_build_cannot_change_snapshot(self):
        def mutate(kit, version, inputs, output):
            self.archive.write_bytes(b'replaced original')
            self.builder(kit, version, inputs, output)
        self.run_install(mutate)
        self.assertEqual(m.verify_installation(self.dest)['tracked_files_verified'],6)

    def test_output_runtime_checked_independently_of_movie(self):
        def bad(kit, version, inputs, output):
            self.builder(kit, version, inputs, output)
            write_zip(output, [('game.dir',version.encode()), ('runtime.dll',b'changed')])
        with self.assertRaises(m.InstallError): self.run_install(bad)
        self.assertFalse(self.dest.exists())

    def test_destination_race_preserves_new_folder(self):
        def race(kit, version, inputs, output):
            self.builder(kit, version, inputs, output)
            self.dest.mkdir(exist_ok=True)
            (self.dest/'saved').write_text('keep')
        with self.assertRaises(FileExistsError): self.run_install(race)
        self.assertEqual([p.name for p in self.dest.iterdir()], ['saved'])

    def test_interrupted_publication_marked_incomplete(self):
        with patch.object(m.shutil, 'move', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError): self.run_install()
        with self.assertRaisesRegex(m.InstallError, 'incomplete'): m.verify_installation(self.dest)

    def test_verify_detects_changed_and_missing_runtime(self):
        self.run_install()
        path=self.dest/'v42/runtime.dll'; path.write_bytes(b'changed')
        with self.assertRaisesRegex(m.InstallError, 'changed'): m.verify_installation(self.dest)
        path.unlink()
        with self.assertRaisesRegex(m.InstallError, 'missing'): m.verify_installation(self.dest)

class PackagingTests(unittest.TestCase):
    def test_committed_allowlist_determinism_and_no_overwrite(self):
        module_path=Path(__file__).resolve().parents[1]/'tools/package_diagnostics.py'
        spec=importlib.util.spec_from_file_location('packager',module_path)
        p=importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); repo=root/'repo'; repo.mkdir()
            def git(*args):
                return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.STDOUT)
            git('init'); git('config','core.autocrlf','false')
            for name in p.FILES.values():
                path=repo/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(name.encode())
            (repo/'game.dir').write_bytes(b'not for distribution')
            git('add','.')
            git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture')
            (repo/'diagnostics/install.py').write_text('uncommitted edit')
            first=root/'one.zip'; second=root/'two.zip'
            p.package(repo,'HEAD',first); p.package(repo,'HEAD',second)
            self.assertEqual(first.read_bytes(),second.read_bytes())
            with zipfile.ZipFile(first) as z:
                self.assertEqual(set(z.namelist()),set(p.FILES)|{'KIT_MANIFEST.json'})
                self.assertEqual(z.read('install.py'),b'diagnostics/install.py')
                json.loads(z.read('KIT_MANIFEST.json'))
            with self.assertRaises(FileExistsError): p.package(repo,'HEAD',first)

if __name__ == '__main__':
    unittest.main()
