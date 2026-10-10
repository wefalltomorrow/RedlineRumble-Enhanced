# v38: bounded visual rear traffic (experiment)

**Status:** Not verified in-game. Built because v36 and v37 crash on the same race, while the v36-camera/v28-traffic no-ghosts diagnostic completed that race. This is strong evidence against unlimited clone retention, **not proof** of the exact crash cause.

## Patch strategy

v35 added models to a list stored in the controller's otherwise unused `mHighway` property (Lingo ID 438), then left the clones in the Director scene until the world shut down. Retention was unlimited.

The v38 builder retains v36's cameras and all other v36 game resources. It makes **one logical resource change: LSCR #1509**.

For either traffic direction, before cloning a car:

1. When `mHighway.count` is below **32**, use the same new-model name generation used by v35.
2. Once the list contains 32, preserve the oldest model's `.name`.
3. Call `W.deleteModel(name)` to remove the oldest scene model. This method and world reference already appear in the original game's traffic script, and are documented Director 3D APIs.
4. Remove the oldest reference using `mHighway.deleteAt(1)`.
5. Clone the next passed vehicle **with the freed name** and attach it to the moving traffic parent using `#preserveWorld`.
6. Append only the visual copy to the list. The original AI, collision, opponent, traffic pool, recycling thresholds, and race progress logic remain unchanged.

Reusing the deleted name is essential. Simply limiting the array count would eventually cause duplicate Director model names.

The maximum is a **test value**, not a scientifically established safe limit. Some original traffic models may have nested children; Director documents that `deleteModel` does not itself delete child objects, so their lifetime must be watched during extended testing.

## Source

`experiments/build_rr_v38.py` uses and patches the **committed** `source/build_redline_v35.py` assembler. It needs the exact historical v28 and v36 user-owned game archives as inputs; neither archive belongs in the Git repository.

```powershell
python experiments/build_rr_v38.py --v28 "RedlineRumble_4K_v28_CameraFix.zip" --v36 "RedlineRumble_4K_v36_RearCamera.zip" --out "RR_v38_GhostCleanup.zip"
```

A local equivalent implementation produced game.dir SHA-256:

`329d95cda176a651b6c868ce66e20301b3fca88b53ab988b2a66734b2c87a119`

The script checks all unrelated resource-map entries, checks the camera resource and compares all other files to v36. It also emits an audit report.

## Windows gameplay test

- Keep the no-ghosts diagnostic build separate; it is the currently surviving comparison.
- Run the same opponent, car and race that crashed on v36 and v37.
- Check v38 rear view (hold `B`), the `C` camera toggle and traffic ahead.
- Look for distant visual cars disappearing when the cap is reached (expected); the previous no-cap behaviour cannot be guaranteed at this limit.
- Complete the **entire race**, ideally more than once. Check memory and native application errors if possible.
- On any Script Error, select **No** and capture the complete verbose message. If it hard-crashes, send the event log, memory CSV and a WER dump.

Do **not** merge v38 on the basis of static validation alone.

Related: [Issue #7](https://github.com/wefalltomorrow/RedlineRumble-Enhanced/issues/7), [v36 no-ghosts PR #8](https://github.com/wefalltomorrow/RedlineRumble-Enhanced/pull/8).
