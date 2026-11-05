# v43 directional reuse diagnostic

v42 stops adding rear visuals once its list reaches 32. v43 keeps updating
rear visuals by reusing models from two independent FIFO pools: 16 same-direction
and 16 oncoming. This is an engineering diagnostic, not a stability release.
v42 remains an untested comparison build; v39 remains the latest player-confirmed
full-race reference. Nothing is merged into main.

## Behavior and scope

The existing property438 holds `[sameDirectionPool, oncomingPool]`, reset at
race initialization. Each direction allocates its first 16 clones under its
own moving parent (401 or 402). Subsequent captures translate the oldest clone
by `source.worldPosition - clone.worldPosition` in `#world` coordinates, then
rotate its list reference to the end. This does not delete or reparent a model
on reuse, assign geometry/materials/transform, or modify gameplay lists.

The clone retains its initial appearance, rotation and scale. A reused rear
visual can therefore differ from the source car, and direction alone is not
full appearance compatibility. Unused slots in one pool cannot serve the other.
This is continuing bounded retention, not unlimited simultaneous visibility.
FIFO reuse can move a clone that is still visible, causing a pop. Matching
origins does not guarantee matching body/pivot alignment.

The exact v28 traffic script is patched and inserted into the exact v36 movie.
All original traffic instructions and branch destinations are checked, with
only branch offsets relocated. Local operands use direct indices0/1/2 as in
v42. Existing local declarations and stack limits remain unchanged; hooks
peak at6 including the existing entry value, within the declared7. The
camera resource1506 and all1599 other mapped resources remain unchanged.
All packaged files apart from game.dir and the version README are preserved.

## Reproduce

Requires Python3.10+ and the user's historical archives, not distributed here.

```powershell
python experiments/build_rr_v43.py --v28 PATH/RedlineRumble_4K_v28_CameraFix.zip --v36 PATH/RedlineRumble_4K_v36_RearCamera.zip --out PATH/RR_v43_DirectionalReuse_Diagnostic.zip
python experiments/test_rr_v43.py -v
python experiments/test_rr_v42.py -v
python tools/audit_game_dir.py PATH/RedlineRumble_4K_v36_RearCamera.zip PATH/RR_v43_DirectionalReuse_Diagnostic.zip --output PATH/audit.json
```

Input game.dir SHA-256:

- v28: `063733277ca3e2a37334fa2c1a9ebfaa310675d5d19a1ded2551b8cf803874d4`
- v36: `771cbb57bb7ee6ef2c19ce23151dd9584e2a0995f90bd43a084237b50638c4ce`

Output game.dir SHA-256:
`d53ac454b425135b6802434b49f77dfb70c1674589be038a50dc47f64a760cc2`.
The ZIP metadata is deterministic for identical input archives. The builder
refuses existing output paths and writes an adjacent validation report.

## Validation limits and playtest

The synthetic VM executes actual emitted instructions through 10,000 randomized
mixed recycling events. It checks allocation bounds, FIFO reuse, independent
pool capacity, world positioning under rotated/scaled parents, source group
integrity, unique names, caller-stack preservation and original index retention.
Other tests cover initialization, empty groups, retained appearance/rotation/scale
and a group crossing the cap mid-loop, plus validation failures (eight tests).
The synthetic transforms are 2D quarter-turns with uniform scaling; reparenting
models position preservation only. This VM models the used opcode/API subset; it is not
Director and cannot establish native implementation or lifetime behavior.

Initialization resets list references; it does not explicitly delete scene
models. Thus the 32-model bound applies per initialized pool, not proven native
memory usage across races. Repeated-race scene cleanup is still an open gate.

Test v42, then v43 with the same race/car in separate folders. Drive beyond
pool saturation in both directions, check B rear view in both C camera modes,
finish/victory/menu, then run a second race without restarting. Check normal
collision behavior, camera return, fullscreen/4K and performance. Record
elapsed time, missing/misplaced visuals and exact script errors or crash logs.
The green truck/checkered flag at victory are normal. Neither the native crash
cause nor original-2003 difficulty equivalence has been established.

## API evidence

Original Lnam1497 independently maps `translate` to133 and `world` to130.
Original Lscr1503 exitFrame0x004b-0x004f uses `45 82 / 42 05 / 67 85`,
corroborating the scalar call and receiver-inclusive argument count. v43 uses
the documented vector overload, with receiver plus two arguments (`args3`).
The [Macromedia dictionary p.684](https://www.manualslib.com/manual/389805/Macromedia-Director-Mx-Lingo-Dictionary.html?page=684)
documents `translate(vector, relativeTo)`; p.685 defines world-coordinate increments.
Its [subtraction section, pp.48-49](https://www.manualshelf.com/manual/macromedia/director-mx-lingo-dictionary/user-guide-english.html)
defines component-wise vector subtraction producing a new vector.
Independent review found no concrete blocker and reproduced the candidate
movie hash; this API evidence still does not constitute native execution.
