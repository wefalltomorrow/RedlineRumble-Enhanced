# v39 hard-cap experiment — why it exists

**In-game evidence:** v36 and v37 both crashed during a full race. The v36-camera/v28-traffic NoGhosts A/B control completed the same race. v38, which allowed at most 32 clones but used `W.deleteModel`, `deleteAt` and reused clone names, also crashed.

This indicates a crash associated with the visual-clone path, **not** that model accumulation alone is proven responsible. In particular, v38 could introduce a different crash through deletion or invalid references. We do not yet have a full crash dump confirming the precise cause.

## v39 changes

Starting from the known v36 camera build and original v28 LSCR #1509 traffic code, this experiment permits up to **32** total visual copies across same-direction and oncoming vehicles. Once the count reaches 32, the game stops creating additional visual copies. It never deletes, recycles or reuses names for those copies.

That separates v38's deletion/name-reuse path from the model creation and attachment paths. The display behind the player will become incomplete in long races; this is expected.

The modified game contains:
- **LSCR #1506** exactly as v36, including `C`/hold-`B` cameras;
- **LSCR #1509** with the above conditional guard around visual cloning;
- All other mapped Director resources and shipped runtime/config files identical to v36;
- Original traffic AI, spawn and collision timing unaffected.

**Important:** v39 is not an established fix. It has passed static bytecode checks, but full-race Windows testing is pending. The built game's expected `game.dir` SHA-256 is:

`73b5bc4e2e57e35abc839eb1a1152d88cb7405be60ee9a7ab7b0748be5a375b5`

## Build with owned source files

```powershell
python experiments/build_rr_v39.py --v28 "RedlineRumble_4K_v28_CameraFix.zip" --v36 "RedlineRumble_4K_v36_RearCamera.zip" --out "RR_v39_HardCap32.zip"
```

The build script imports [the v35 builder](../source/build_redline_v35.py) from the repository and rejects unexpected source hashes. Proprietary Director/game files are not committed to GitHub.

## How to test

Play the exact car/opponent/race that crashed in v36–v38. Keep this in a separate folder. If it crashes, collect the **new** Application Error/WER entry (faulting module and offset), any `.dmp` and `MemoryUsage.csv`.

- **If v39 completes:** v38's deletion/name-reuse path or continued clone churn become stronger suspects; repeat before deciding which.
- **If v39 crashes:** fewer, never-deleted models still trigger the issue, suggesting cloning, hierarchy/parenting or other shared runtime effects need isolation.
- **If both modes behave inconsistently:** repeat the same race several times; a single success isn't proof of full stability.

Track evidence in [Issue #7](https://github.com/wefalltomorrow/RedlineRumble-Enhanced/issues/7). Do not merge into `main` based on static validation.
