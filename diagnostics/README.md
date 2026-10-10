# Crash isolation: v36 camera, original v28 traffic

The user reported a crash in the same race on **v36 and v37**. Therefore the v37-only Z-scale modification cannot, by itself, explain every crash. The previous v37 event (Projector.exe / IML32.dll, 0xC0000005 at RVA 0x10CCD) does **not** establish that the v36 crash had the same error or call stack.

## Hypothesis to isolate

v35 introduced uncapped, undeleted visual-only copies of passed traffic models in script resource 1509. v36 and v37 inherit this code. These models could accumulate during a long race; the source confirms no count or cleanup, but we do **not** yet know whether accumulation causes the native crash.

## Diagnostic A/B build

Use [`build_v36_no_ghosts.py`](build_v36_no_ghosts.py) with your own existing, unmodified source ZIP files. **No original game binaries or DLLs are stored in this repository.**

```powershell
python diagnostics/build_v36_no_ghosts.py --v28 "RedlineRumble_4K_v28_CameraFix.zip" --v36 "RedlineRumble_4K_v36_RearCamera.zip" --out "RR_v36_NoGhosts_AB.zip"
```

The output keeps original v36 camera script **1506**, restores original v28 traffic script **1509**, and otherwise retains every resource and non-`game.dir` runtime/config file from v36. No road or traffic difficulty adjustments are made.

SHA-256 checks reject unexpected source binaries. The output includes an audit JSON.

## How to interpret the result

- **v36 crashes, diagnostic completes:** the visual clone addition becomes the stronger suspect; next implement lifecycle/lifetime tracking rather than merely choosing a large arbitrary cap.
- **Both crash:** investigate common camera, rendering or runtime behaviour; compare with an untouched v28/v22 run.
- **Both complete on retry:** treat earlier failures as intermittent and repeat before inferring causation.

Use the **same full race, car, opponent, camera settings and renderer configuration**. Keep folders separate and capture the Director debug log plus Windows Application Error 1000/WER 1001, full WER dump if available, and memory samples from `RR_CrashCapture.ps1`.

**Expected regression:** cars will disappear behind the car as they do in v28, because the rear visual retention system is deliberately disabled. That's the independent variable; the v36 cameras must continue to work.

This is a controlled diagnostic, **not a verified full-race stable release**. Track results in [Issue #7](https://github.com/wefalltomorrow/RedlineRumble-Enhanced/issues/7). Do not merge until the diagnostic has been tested.
