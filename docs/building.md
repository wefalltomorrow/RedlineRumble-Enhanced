# Building locally

The scripts are **binary patchers** for Macromedia Director resources. They are not a complete source-code compilation system.

## Requirements

- Python 3.10+ (standard library only for the patch scripts)
- Your own game and runtime files
- Exact historical snapshots of the v22 and v26 game modifications used to create the verified v28 base, or an already-verified v28 ZIP

The repository intentionally does not contain original game files, Director runtimes, game textures/sounds, or third-party graphics DLLs.

## Input layout

For a full reproduction of the development chain, place the historical snapshots in the following local folders:

```text
source/
  historical/
    files/
      080-RedlineRumble_4K_v22/
        game.dir
        ... other runtime files ...
      099-RedlineRumble_4K_v26_Cameras_StockRestore/
        game.dir
        ... other files ...
```

The folder names correspond to archived development snapshots. They are not downloadable from this repository. The build will stop if the expected game file SHA-256 hash does not match.

## Build sequence

From the repository root, run:

```powershell
python source/build_redline_v28.py
python source/build_redline_v35.py
python source/build_redline_v36.py
```

Outputs appear in `source/`:

- `RedlineRumble_4K_v28_CameraFix.zip`
- `RedlineRumble_4K_v35_TrafficFix.zip`
- `RedlineRumble_4K_v36_RearCamera.zip`

Each build writes its own `RedlineRumble_vNN_validation.json` file. v35 consumes the v28 ZIP; v36 consumes the v35 ZIP. Do not rename these inputs.

If you already have a verified v28 ZIP, place it directly in `source/` and start with v35. Don't replace the expected hash with a random build hash to bypass compatibility checks.

## Static checks

These tests do not require game binaries:

```powershell
python tests/test_redline_v36.py
python -m compileall -q source tests
```

With the appropriate input/output ZIPs available, also run:

```powershell
python tests/test_redline_v35.py
```

These checks validate bytecode structure, expected resource changes, and input-state simulations; they **cannot guarantee** that Director will run correctly. Gameplay testing on Windows is still required.

## What to test in-game

Verify `C`, hold/release `B` from both views, switching while `B` is held, passing cars and viewing them behind, traffic frequency ahead, collisions, completion conditions and performance. Preserve your last known working build.

## Distribution

Only scripts, docs and non-proprietary tests are committed here. A redistributable binary patch format and release packaging workflow are future work.