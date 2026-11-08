import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import install
import record_session as r

def row(kind, **data): return {'kind':kind,'utc':'2026-11-08T00:00:00Z','data':data}

def event(path, pid='0x123', field='AppPath'):
    return ('<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
            '<System><EventID>1000</EventID><EventRecordID>7</EventRecordID></System><EventData>'
            f'<Data Name="{field}">{path}</Data><Data Name="ProcessId">{pid}</Data>'
            '<Data Name="ExceptionCode">c0000005</Data></EventData></Event>')

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.session={'build':'v42','source_commit':'fixture','executable':r'C:\game\Projector.exe'}

    def test_normal_exit_never_asserts_gameplay_pass(self):
        result=r.summarize([row('attached',process_id=291),row('exited',exit_code=0),row('observer_finished')],self.session)
        self.assertEqual(result['process_outcome'],'exit_code_zero')
        self.assertEqual(result['gameplay_result'],'unverified')

    def test_signed_native_exit_code_and_memory(self):
        result=r.summarize([row('sample',private_bytes=300),row('sample',private_bytes=900),
                            row('sample',private_bytes=400),row('exited',exit_code=-1073741819)],self.session)
        self.assertEqual(result['exit_code_hex'],'0xC0000005')
        self.assertEqual(result['private_bytes_peak'],900)
        self.assertEqual(result['private_bytes_last'],400)

    def test_not_observed_timeout_stop_and_error_are_not_exits(self):
        for kind in ('not_observed','stopped','time_limit','observer_error'):
            result=r.summarize([row(kind)],self.session)
            self.assertIsNone(result['exit_code'])
            self.assertNotIn(result['process_outcome'],('exit_code_zero','exit_code_nonzero'))

    def test_event_path_and_pid_correlation(self):
        path=self.session['executable']
        self.assertIsNotNone(r.parse_event(event(path),path,291))
        self.assertIsNone(r.parse_event(event(r'C:\other\Projector.exe'),path,291))
        self.assertIsNone(r.parse_event(event(path,'0x124'),path,291))
        self.assertIsNone(r.parse_event(event('Projector.exe'),path,291))
        self.assertEqual(r.parse_event(event(path,'unknown'),path,291)['correlation'],'same_path_in_session_window')

    def test_bad_event_is_reported_without_losing_exit(self):
        result=r.summarize([row('windows_event',xml='bad'),row('exited',exit_code=7)],self.session)
        self.assertEqual(len(result['event_parse_errors']),1)
        self.assertEqual(result['exit_code'],7)

    def test_preflight_uses_known_profile_not_installation_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); kit=root/'kit'; kit.mkdir(); game=root/'installation/v42'; game.mkdir(parents=True)
            (game/'game.dir').write_bytes(b'known'); (game/'Projector.exe').write_bytes(b'fixture')
            expected=install.file_records(game)
            (kit/'profiles.json').write_text(json.dumps({'builds':{'v42':{'files':expected}}}))
            (kit/'KIT_MANIFEST.json').write_text(json.dumps({'format':'redline-source-kit-v1',
                'source_commit':'fixture','files':install.file_records(kit)}))
            good=r.preflight(kit,game.parent,'v42')
            self.assertEqual(good['baseline_files_verified'],2)
            (game/'game.dir').write_bytes(b'wrong')
            with self.assertRaises(install.InstallError):r.preflight(kit,game.parent,'v42')

    def test_markers_are_explicit_user_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'markers').mkdir()
            r.write_json(root/'SESSION.json',{'format':'redline-session-v1'})
            marker=r.add_marker(root,'race1_finished','Saw victory screen')
            self.assertEqual(marker['source'],'user_reported')
            self.assertEqual(len(list((root/'markers').iterdir())),1)

    def test_finalize_reports_changes_and_preserves_existing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); game=root/'game'; game.mkdir(); (root/'markers').mkdir()
            (game/'a').write_bytes(b'old'); before=install.file_records(game)
            (game/'a').write_bytes(b'new'); (game/'b').write_bytes(b'added')
            session={**self.session,'game_folder':str(game),'files_before':before}
            result=r.finalize(root,[],session)
            self.assertEqual(result['changed_files'],['a']); self.assertEqual(result['added_files'],['b'])
            with self.assertRaises(FileExistsError):r.finalize(root,[],session)

@unittest.skipUnless(os.name=='nt' and shutil.which('powershell.exe'),'Windows PowerShell integration')
class NativeObserverTests(unittest.TestCase):
    def test_complete_recorder_cli_no_game_started(self):
        with tempfile.TemporaryDirectory(prefix='rr session ') as tmp:
            root=Path(tmp); kit=root/'kit'; kit.mkdir(); game=root/'RR_Diagnostic_Comparison/v42'; game.mkdir(parents=True)
            for name in ('install.py','record_session.py','watch_process.ps1'):
                shutil.copyfile(Path(__file__).with_name(name),kit/name)
            (game/'Projector.exe').write_bytes(b'not an executable; observer must never launch it')
            (game/'game.dir').write_bytes(b'fixture')
            (kit/'profiles.json').write_text(json.dumps({'builds':{'v42':{'files':install.file_records(game)}}}))
            (kit/'KIT_MANIFEST.json').write_text(json.dumps({'format':'redline-source-kit-v1','source_commit':'fixture',
                                                           'files':install.file_records(kit)}))
            command=[sys.executable,'-B',str(kit/'record_session.py'),'--quick','--wait-seconds','1']
            done=subprocess.run(command,capture_output=True,text=True,timeout=30)
            self.assertEqual(done.returncode,0,done.stderr)
            sessions=list((root/'RR_Playtest_Sessions').iterdir())
            self.assertEqual(len(sessions),1); session=sessions[0]
            result=json.loads((session/'RESULT.json').read_text())
            self.assertEqual(result['process_outcome'],'exit_not_observed')
            self.assertEqual(result['sample_count'],0)
            self.assertTrue(result['observer_finished'])
            self.assertEqual(result['changed_files'],[])
            self.assertFalse((session/'RECORDING_INCOMPLETE.txt').exists())
            self.assertIn(result['events_status'][0]['status'],('queried','unavailable'))
            again=subprocess.run(command+['--out',str(session)],capture_output=True,text=True,timeout=15)
            self.assertNotEqual(again.returncode,0)

    def observe(self, code=None, stop=False, timeout=False):
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'STOP'
            command=['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',
                     str(Path(__file__).with_name('watch_process.ps1')),'-Executable',sys.executable,
                     '-StopFile',str(marker),'-WaitSeconds','2','-RunSeconds','1' if timeout else '5',
                     '-IntervalMs','100','-SkipEvents']
            observer=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8-sig',
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            target=None
            try:
                first=observer.stdout.readline()
                self.assertTrue(first,observer.stderr.read() if observer.poll() is not None else 'No ready record')
                ready=json.loads(first); self.assertEqual(ready['kind'],'ready')
                self.assertIn(os.getpid(),ready['data']['ignored_existing_process_ids'])
                rows=[ready]
                if code is not None:
                    delay=10 if stop or timeout else 0.8
                    target=subprocess.Popen([sys.executable,'-c',f'import time,sys; time.sleep({delay}); sys.exit({code})'],
                                            creationflags=subprocess.CREATE_NO_WINDOW)
                    while True:
                        line=observer.stdout.readline()
                        self.assertTrue(line,'Observer ended before attachment')
                        rows.append(json.loads(line))
                        if rows[-1]['kind']=='attached': break
                    self.assertEqual(rows[-1]['data']['process_id'],target.pid)
                    if stop: marker.write_text('stop observing')
                stdout,stderr=observer.communicate(timeout=20)
                self.assertEqual(observer.returncode,0,stderr)
                rows.extend(json.loads(line) for line in stdout.splitlines() if line)
                if stop or timeout: self.assertIsNone(target.poll(),'Observer must leave target running')
                return rows
            finally:
                if observer.poll() is None: observer.kill(); observer.wait()
                observer.stdout.close(); observer.stderr.close()
                # Only the synthetic child launched by this test is stopped.
                if target is not None:
                    if target.poll() is None: target.terminate()
                    target.wait()

    def test_real_process_exit_zero_and_samples(self):
        rows=self.observe(0)
        self.assertTrue(any(x['kind']=='sample' for x in rows))
        self.assertEqual([x['data']['exit_code'] for x in rows if x['kind']=='exited'],[0])

    def test_real_process_nonzero_exit(self):
        self.assertEqual([x['data']['exit_code'] for x in self.observe(7) if x['kind']=='exited'],[7])

    def test_no_new_process(self):
        self.assertIn('not_observed',[x['kind'] for x in self.observe()])

    def test_stop_leaves_target_running(self):
        self.assertIn('stopped',[x['kind'] for x in self.observe(0,stop=True)])

    def test_time_limit_leaves_target_running(self):
        self.assertIn('time_limit',[x['kind'] for x in self.observe(0,timeout=True)])

if __name__=='__main__': unittest.main()
