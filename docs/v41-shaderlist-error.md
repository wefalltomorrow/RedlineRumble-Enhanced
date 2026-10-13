# v40 error analysis and v41 diagnostic

**User recording:** `bandicam 2026-10-13 21-36-54-075.mp4` (73.92 s; captured at 1920×1080, approximately 60 fps).

**Observed:** v40 started normally and entered a race. At about 55 seconds a blocking **Director Player Error** dialog appeared:

> Property not found  
> `#shaderList`  
> Script Error. Continue?

The dialog remains visible through the remainder of the recording. **This was a Lingo runtime error, not evidence of a native exception, Windows process crash or finished race.**

**Likely trigger:** v40's `pooled_clone()` method reads and assigns `shaderList` on a car model during the oldest-model-reuse path when 32 ghosts exist. v39 (32 clone hard cap, no reuse) was confirmed to finish a complete race.

## v41 scope

v41 removes **only** the `shaderList` read/set operation from the reuse path. It retains the v40 fixed-pool idea and its `resource`, `transform` and `worldPosition` operations, all of which remain **unproven safe** on this exact runtime/object hierarchy. Thus v41 is strictly a diagnostic, not a gameplay fix.

The builder reproduces v40's known `game.dir` hash before constructing the modified movie:

- v40 hash: `7d3038fcdea01d85f741f31f023075a8a6ad28175291f5c46e1033f65f73a056`.
- v41 hash: `e0e3542f4c95f17ddcc37c854ed1a3acda4cefefab112710ba11150c581d0c7a`.
- Only LSCR **1509** differs from v36; camera LSCR **1506**, all other resource-map records, other game assets and runtime DLLs remain unchanged.

Build using owned original v28/v36 archives:

```powershell
python experiments/build_rr_v41.py --v28 "RedlineRumble_4K_v28_CameraFix.zip" --v36 "RedlineRumble_4K_v36_RearCamera.zip" --out "RR_v41_NoShaderList_Diagnostic.zip"
```

The script aborts on input hash mismatch or incompatible output; it doesn't contain original game assets.

## Fullscreen information

The separate `FullscreenFix_v18.log` recorded a successful borderless window change from game window `(-14,-65) 3868×2192`, client `3840×2113`, to `(0,0) 3840×2160` with client `3840×2160`. It reported 30 consecutive correct geometry observations from 21:37:03 to 21:37:18 and no helper error. This demonstrates success **during that observation period**, not indefinite stability or a connection to v40's `#shaderList` script error.

## Test / next decision

- Test in a separate directory, **do not overwrite v39**.
- Drive past enough traffic to hit the pool cap and reuse an old model.
- Check for any new Script Error (including `#worldPosition`, `#transform`, `#resource`). If seen, choose **No** and send full text/screenshots.
- Watch for wrong car skins, displaced traffic models, frame drops, a native crash or broken victory transition.
- Don't mark v41 as successful until the full race reaches the winner screen and menu, including repeat runs.

Related: [v40 failing PR #11](https://github.com/wefalltomorrow/RedlineRumble-Enhanced/pull/11), [crash investigation #7](https://github.com/wefalltomorrow/RedlineRumble-Enhanced/issues/7).
