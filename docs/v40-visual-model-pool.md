# v40 — Fixed-pool visual rear traffic (experimental)

## Why

User tests on **12 October 2026** confirm v39 completed a full race, displayed the normal win scene and returned to the menu without crashing. The green truck/checkered flag in the win scene are normal game behaviour, **not a graphics bug**.

Earlier findings:
- v36/v37, retaining uncapped rear clones, crashed.
- v38, deleting/replacing models at a 32-object limit, crashed.
- v39, creating no more than 32 rear clones and never deleting any of them, finished the problematic race.
- v39 eventually stops retaining new cars behind the player, a visible limitation.

## v40 experiment

Keep the **same 32 Director 3D objects** after pool fill. At the next traffic recycle event:

1. Read the oldest model object from the existing `mHighway` list.
2. Read the newly recycling car model from the original traffic code.
3. Assign its `resource` (geometry), `shaderList`, `transform`, and `worldPosition` (world vector) to the existing ghost object.
4. Rotate the reference list using **list.deleteAt(1)** and **list.add(reusedModel)**, with no `W.deleteModel`, no model-name reuse, and no further `clone` or `addChild` calls after filling the pool.

All original traffic simulation, collision and race logic remains unchanged. Camera LSCR #1506 remains as in user-tested v36/v39. Only traffic LSCR #1509 is patched.

**Important limitations:** This is a static construction, not an in-game verified implementation. Director might reject these setters, a transformed model might have mismatched child geometry (e.g. wheels) when changing vehicle types, and incorrectly reparented transformations could visibly teleport cars. The ring pool also cannot preserve *unlimited* historical cars behind: old copies are repurposed rather than retained forever. Avoid overstating it as infinite render distance.

## Source and verification

[Builder](../experiments/build_rr_v40.py) · [Source-only tests](../experiments/test_rr_v40.py)

The builder requires the exact hash-verified v28/v36 ZIP snapshots and imports `source/build_redline_v35.py`. It compares its generated `game.dir` against the independently validated SHA-256:

`7d3038fcdea01d85f741f31f023075a8a6ad28175291f5c46e1033f65f73a056`

Use:

```powershell
python experiments/build_rr_v40.py --v28 "RedlineRumble_4K_v28_CameraFix.zip" --v36 "RedlineRumble_4K_v36_RearCamera.zip" --out "RR_v40_PooledGhosts_Experimental.zip"
```

The compiled local ZIP passed CRC checks; camera resource 1506 and all 1,599 other mapped resource records matched v36, and non-game files were byte-identical. Five separate local Python regression tests passed; repository CI covers source-level tests without needing proprietary inputs.

## Windows playtest criteria

Extract to a **new folder** and keep v39 intact. On the same opponent/car/race:

- Verify cameras and hold/release `B` still work.
- Verify the first 32 retained cars behave as in v39.
- Continue driving past at least 32 recycle events; check whether older visual cars reposition cleanly and display the correct vehicle meshes/textures.
- Check for model overlap, distorted wheel/child meshes, lane misalignment or sudden forward collisions.
- Complete the entire race, see the normal winner sequence, return to main menu.
- If it crashes, capture the new Windows Application Error event, process memory CSV, Director verbose error and `.dmp` if present.

Keep this PR **draft and unmerged** until the complete test passes. The previous v39 build is our confirmed full-race result; the no-ghosts build remains the no-cloning control.

Related: [Crash investigation #7](https://github.com/wefalltomorrow/RedlineRumble-Enhanced/issues/7) and [v39 PR #10](https://github.com/wefalltomorrow/RedlineRumble-Enhanced/pull/10).
