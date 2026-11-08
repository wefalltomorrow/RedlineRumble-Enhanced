# Redline Rumble diagnostic comparison kit

This source-only kit installs the existing v42 and v43 diagnostics into separate
new folders. Both remain **gameplay-unverified**. v39 is the player-confirmed
full-race/victory/menu reference. This is not a stable release or a new game patch.

## Requirements

Use Python 3.10+ on Windows and your own recovered v28, v36 and v39 ZIPs. No pip
packages are needed. This kit contains no game, assets or runtime binaries.
The original combined conversation archive is not needed. Keep your individual
baseline ZIPs for future reproduction.

Extract the entire kit to a fresh folder. Run from that folder in PowerShell:

~~~powershell
python -B install.py --build comparison --v28 "C:\archives\015-RedlineRumble_4K_v28_CameraFix.zip" --v36 "C:\archives\062-RedlineRumble_4K_v36_RearCamera.zip" --v39 "C:\archives\103-RR_v39_HardCap32.zip" --out "C:\Games\RR-Comparison"
~~~

Replace these example paths. The output folder must not exist. To build only
v42, use --build v42 --v39 ... --out ...; for v43 use
--build v43 --v28 ... --v36 ... --out ... .

Every input file is checked against recovered baseline sizes and SHA-256 hashes,
including DLLs and launchers. ZIP timestamps and compression may differ, but
missing, extra or changed payload files stop installation. Inputs are copied to
private temporary snapshots before validation. The builders then produce the
previously verified diagnostic movies. Existing build folders are never replaced.

The kit checks its source manifest and rejects extra files. Keep notes outside
the kit; if you imported its modules and created __pycache__, extract a fresh
copy. Manifests detect accidental changes; they are not digital signatures.

## Playtest

Open v42 or v43 in the installed folder and run its existing .cmd launcher.
The installer never launches the game. Test v42 first, then v43 using the same
race/car. Record results in the editable TEST_RESULTS.txt.

Check rear traffic after saturation, both C camera modes and held/released B,
collisions, race finish/victory/menu, and a second race without restarting.
v42 retains the 32-clone cap. v43 reuses two pools of 16 clones and can show
appearance mismatches or visible FIFO repositioning. Neither has proven native
stability or repeated-race cleanup. Cameras, difficulty and runtime files are
unchanged from their respective diagnostic builds.

Separate folders still use Director's shared save/profile. The installer does
not alter or isolate that save. The green truck/checkered flag at victory are normal.

## Verify later

~~~powershell
python -B install.py --verify "C:\Games\RR-Comparison"
~~~

INSTALLATION.json records the source commit, input archive hashes, installed
file hashes and build reports. Verification checks all recorded runtime files
and reports extra files. TEST_RESULTS.txt is intentionally editable and is
excluded from hash checking. Changes from normal play are changes since install,
not proof of corruption. The manifest records no gameplay approval.

If publication was interrupted, a new folder can remain with
INSTALLATION_INCOMPLETE.txt. Do not use it as a verified installation; retry
with another new destination. Original inputs and existing builds are preserved.

## Reproduce the source kit

From the repository, commit the intended source and run:

~~~powershell
python tools/package_diagnostics.py --ref COMMIT_SHA --out "C:\output\RR_Diagnostic_Source_Kit.zip"
python -B -m unittest discover -s diagnostics -p "test_*.py" -v
~~~

The packager reads a fixed source allowlist from Git, ignores uncommitted edits,
records the resolved commit and uses fixed ZIP metadata without compression.
The same commit produces identical kit bytes. It refuses an existing ZIP path.

## Record a native playtest

For the prepared comparison layout, double-click Record_v42.cmd or
Record_v43.cmd in the kit. This requires Python on PATH and expects a sibling
RR_Diagnostic_Comparison folder. A uniquely named session is created under
the sibling RR_Playtest_Sessions folder. Wait for READY, then launch the game
using its existing launcher. The recording console stays open to show results.

The kit also includes a Windows PowerShell 5.1 observer. It runs without admin
access, leaves the original launcher intact, and does not launch or stop the
game, attach a debugger, change registry/WER settings, or collect crash dumps.
It supersedes the archived v36/v37 collector for basic process evidence; it
does not replace that collector's optional full-dump capability.

From the extracted kit, start a new recording:

~~~powershell
python -B record_session.py --installation "C:\Games\RR-Comparison" --build v42 --out "C:\RR-Sessions\v42-first"
~~~

When READY appears, launch the existing .cmd in the selected v42 folder. The
recorder waits up to 180 seconds for a **new** process at that exact executable
path. Already running instances are ignored. Keep the recorder open while you
play both races and exit the game normally. Repeat with --build v43 and a new
session folder. Optional --wait-seconds and --run-seconds set the wait and run
limits (defaults: 180 and 7200 seconds). A recording timeout leaves the game running.

Run the same command with --preflight and without --out for file checks only.
The baseline runtime is hash-checked before recording. Extra files, including
graphics wrappers installed by the existing launcher, are recorded by name,
size and hash; their presence is not an authenticity or compatibility approval.

To annotate a running session from another terminal:

~~~powershell
python -B record_session.py --mark "C:\RR-Sessions\v42-first" --label race1_finished --note "Victory screen appeared; race/car: ..."
python -B record_session.py --stop "C:\RR-Sessions\v42-first"
~~~

Markers include race1_started, race1_finished, menu_returned, race2_started,
race2_finished, rear_traffic_checked, cameras_checked, script_error and note.
They are explicitly user-reported. Markers added after finalization stay in
the markers folder; RESULT.json contains the snapshot at finalization.
The stop command ends observation only. You can instead keep observations in
the comparison installation's TEST_RESULTS.txt.

Each new session contains SESSION.json (build and file hashes), observer.jsonl
(flushed process/memory/module observations), observer.stderr.txt, RESULT.json,
and MemoryUsage.csv when samples exist. Files changed/added/missing during the
session are reported. Process module paths are recorded without reading process
memory. Everything stays local; nothing is uploaded by the recorder.

Windows Application events 1000/1001/1002 are queried only within the observation
window and retained only when structured data contains the exact executable
path. Where a process ID exists, the summary rejects a different ID. Events
without IDs are labeled weaker path/time matches. Missing path data, delayed
events, access failures and the 200-event query cap can prevent capture; a query
status is included. No matching event does not mean no crash occurred.

A zero process exit code is not a passed race or proof that no Director script
error occurred. Memory growth alone does not prove a leak. Gameplay remains
unverified until the actual observations establish the result. If recording
is interrupted, keep the JSONL and the RECORDING_INCOMPLETE marker for diagnosis.
