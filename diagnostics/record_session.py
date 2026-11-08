#!/usr/bin/env python3
"""Record a manually launched diagnostic; never launch or stop the game."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

import install

MARKERS = ('race1_started', 'race1_finished', 'menu_returned', 'race2_started',
           'race2_finished', 'rear_traffic_checked', 'cameras_checked', 'script_error', 'note')

def utc():
    return datetime.now(timezone.utc).isoformat()

def write_json(path, data):
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, indent=2); f.write('\n')

def preflight(kit, installation, version):
    manifest = install.verify_kit(kit)
    profiles = install.read_json(kit/'profiles.json')
    folder = installation.resolve()/version
    install.verify_files(folder, profiles['builds'][version]['files'])
    actual = install.file_records(folder)
    extras = {k:v for k,v in actual.items() if k not in profiles['builds'][version]['files']}
    return {'format':'redline-session-v1', 'created_utc':utc(), 'build':version,
            'source_commit':manifest['source_commit'], 'game_folder':str(folder),
            'executable':str(folder/'Projector.exe'),
            'baseline_files_verified':len(profiles['builds'][version]['files']),
            'files_before':actual, 'extra_files':extras,
            'graphics_wrapper_present':'D3D9.dll' in actual,
            'gameplay_result':'unverified', 'game_launched_by_recorder':False}

def parse_event(xml, executable, process_id):
    """Exact path and optional PID correlation; no localized message matching."""
    root = ET.fromstring(xml)
    ns = {'e':'http://schemas.microsoft.com/win/2004/08/events/event'}
    fields = {n.get('Name',''):n.text or '' for n in root.findall('e:EventData/e:Data',ns)}
    norm = lambda x: x.strip().strip('"').replace('/', '\\').casefold()
    if norm(executable) not in {norm(v) for v in fields.values()}:
        return None
    lower = {k.casefold():v for k,v in fields.items()}
    pid_text = lower.get('processid')
    match = 'same_path_in_session_window'
    if pid_text:
        try:
            event_pid = int(pid_text,16 if pid_text.lower().startswith('0x') else 10)
        except ValueError:
            event_pid = None
        if process_id is not None and event_pid is not None:
            if event_pid != process_id: return None
            match = 'same_path_and_pid_in_session_window'
    system = root.find('e:System',ns)
    return {'event_id':system.findtext('e:EventID', namespaces=ns),
            'record_id':system.findtext('e:EventRecordID', namespaces=ns),
            'correlation':match, 'fields':fields}

def summarize(records, session):
    attached = [r['data'] for r in records if r['kind']=='attached']
    exits = [r['data'] for r in records if r['kind']=='exited']
    samples = [r for r in records if r['kind']=='sample']
    kinds = {r['kind'] for r in records}
    process_id = attached[0]['process_id'] if len(attached)==1 else None
    code = exits[-1].get('exit_code') if exits else None
    outcome = ('exit_code_zero' if code==0 else 'exit_code_nonzero') if code is not None else 'exit_not_observed'
    if 'ambiguous' in kinds: outcome='ambiguous_processes'
    if 'observer_error' in kinds: outcome='observer_error'
    events, parse_errors = [], []
    for r in records:
        if r['kind']=='windows_event':
            try:
                event=parse_event(r['data']['xml'],session['executable'],process_id)
                if event: events.append(event)
            except (ET.ParseError, AttributeError, KeyError) as e: parse_errors.append(str(e))
    memory = [r['data']['private_bytes'] for r in samples]
    return {'format':'redline-session-result-v1', 'build':session['build'],
            'source_commit':session['source_commit'], 'process_id':process_id,
            'process_outcome':outcome, 'exit_code':code,
            'exit_code_hex':f'0x{code & 0xffffffff:08X}' if code is not None else None,
            'sample_count':len(samples), 'private_bytes_first':memory[0] if memory else None,
            'private_bytes_last':memory[-1] if memory else None,
            'private_bytes_peak':max(memory) if memory else None,
            'events':events, 'event_parse_errors':parse_errors,
            'events_status':[r['data'] for r in records if r['kind']=='events_status'],
            'observer_errors':[r for r in records if r['kind'] in ('observer_error','sample_error','process_access_error')],
            'observer_finished':'observer_finished' in kinds,
            'gameplay_result':'unverified',
            'limitations':['Zero exit code does not prove a completed race or absence of script errors.',
                          'Memory growth does not identify a leak or its cause.',
                          'Events can be delayed, unavailable, truncated or lack the exact executable path.',
                          'No crash dump, debugger attachment or native call stack is collected.']}

def add_marker(folder, label, note):
    session=install.read_json(folder/'SESSION.json')
    if session.get('format')!='redline-session-v1': raise install.InstallError('Not a session folder')
    marker={'utc':utc(),'label':label,'note':note,'source':'user_reported'}
    write_json(folder/'markers'/f'{uuid.uuid4().hex}.json',marker)
    return marker

def finalize(folder, records, session):
    result=summarize(records,session)
    result['user_markers']=sorted([install.read_json(p) for p in (folder/'markers').glob('*.json')],key=lambda x:x['utc'])
    try:
        after=install.file_records(Path(session['game_folder']))
        before=session['files_before']
        result['files_after']=after
        result['changed_files']=sorted(n for n in before if n in after and before[n]!=after[n])
        result['missing_files']=sorted(set(before)-set(after))
        result['added_files']=sorted(set(after)-set(before))
    except (OSError,install.InstallError) as e: result['postcheck_error']=str(e)
    write_json(folder/'RESULT.json',result)
    samples=[{'utc':r['utc'],**r['data']} for r in records if r['kind']=='sample']
    if samples:
        with (folder/'MemoryUsage.csv').open('x',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(samples[0])); writer.writeheader(); writer.writerows(samples)
    return result

def record(kit, installation, version, output, wait_seconds, run_seconds):
    if os.name!='nt': raise install.InstallError('Native observation requires Windows')
    powershell=shutil.which('powershell.exe')
    if not powershell: raise install.InstallError('Windows PowerShell was not found')
    session=preflight(kit,installation,version)
    output=output.absolute()
    if output.resolve().is_relative_to(installation.resolve()) or output.resolve().is_relative_to(kit.resolve()):
        raise install.InstallError('Keep session output outside the game installation and source kit')
    output.mkdir(parents=True,exist_ok=False)
    (output/'markers').mkdir()
    write_json(output/'SESSION.json',session)
    incomplete=output/'RECORDING_INCOMPLETE.txt'
    incomplete.write_text('Recording has not finalized. Keep observer.jsonl if interrupted.\n',encoding='utf-8')
    records=[]
    command=[powershell,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(kit/'watch_process.ps1'),
             '-Executable',session['executable'],'-StopFile',str(output/'STOP'),
             '-WaitSeconds',str(wait_seconds),'-RunSeconds',str(run_seconds)]
    print(f'Recording folder: {output}',flush=True)
    with (output/'observer.jsonl').open('x',encoding='utf-8') as log, (output/'observer.stderr.txt').open('x',encoding='utf-8') as err:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8-sig',
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for line in process.stdout:
                log.write(line); log.flush()
                try: row=json.loads(line)
                except ValueError:
                    row={'kind':'observer_error','utc':utc(),'data':{'error':'Non-JSON observer output'}}
                records.append(row)
                if row['kind']=='ready':
                    print(f'READY: launch the existing .cmd in {session["game_folder"]}.',flush=True)
                    if row['data']['ignored_existing_process_ids']:
                        print('Already running instances are ignored. Start a NEW game instance.',flush=True)
                elif row['kind'] in ('attached','exited','not_observed','stopped','time_limit','ambiguous','observer_error'):
                    print(json.dumps(row),flush=True)
            return_code=process.wait()
            if return_code:
                records.append({'kind':'observer_error','utc':utc(),'data':{'helper_exit_code':return_code}})
        except KeyboardInterrupt:
            if not (output/'STOP').exists(): (output/'STOP').write_text('User interrupted recorder',encoding='utf-8')
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired: process.terminate(); process.wait()
            records.append({'kind':'observer_error','utc':utc(),'data':{'error':'Recording interrupted; target was not terminated'}})
        finally: process.stdout.close()
    result=finalize(output,records,session)
    incomplete.unlink()
    print(json.dumps({k:result[k] for k in ('process_outcome','exit_code_hex','sample_count','gameplay_result')},indent=2))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installation',type=Path)
    p.add_argument('--build',choices=('v42','v43'),default='v42')
    p.add_argument('--out',type=Path)
    p.add_argument('--preflight',action='store_true')
    p.add_argument('--quick',action='store_true',help='Use sibling RR_Diagnostic_Comparison and create a unique sibling session')
    p.add_argument('--wait-seconds',type=int,default=180)
    p.add_argument('--run-seconds',type=int,default=7200)
    actions=p.add_mutually_exclusive_group()
    actions.add_argument('--mark',type=Path,metavar='SESSION')
    actions.add_argument('--stop',type=Path,metavar='SESSION')
    p.add_argument('--label',choices=MARKERS,default='note')
    p.add_argument('--note',default='')
    a=p.parse_args()
    try:
        if a.mark: print(json.dumps(add_marker(a.mark,a.label,a.note),indent=2))
        elif a.stop:
            if install.read_json(a.stop/'SESSION.json').get('format')!='redline-session-v1':
                raise install.InstallError('Not a session folder')
            with (a.stop/'STOP').open('x',encoding='utf-8') as f: f.write(utc())
            print('Recorder stop requested. The game is left running.')
        else:
            kit=Path(__file__).resolve().parent
            if a.quick:
                if not a.installation: a.installation=kit.parent/'RR_Diagnostic_Comparison'
                if not a.out:
                    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                    a.out=kit.parent/'RR_Playtest_Sessions'/f'{a.build}_{stamp}_{uuid.uuid4().hex[:8]}'
            if not a.installation: p.error('--installation is required')
            if not 1<=a.wait_seconds<=3600 or not 1<=a.run_seconds<=86400: p.error('Invalid recording duration')
            if a.preflight: print(json.dumps(preflight(kit,a.installation,a.build),indent=2))
            else:
                if not a.out: p.error('--out NEW_SESSION_FOLDER is required')
                record(kit,a.installation,a.build,a.out,a.wait_seconds,a.run_seconds)
    except (OSError,ValueError,KeyError,TypeError) as exc: p.exit(1,f'Recording stopped: {exc}\n')

if __name__=='__main__': main()
