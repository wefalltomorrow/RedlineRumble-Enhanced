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
