# Forward traffic and road-horizon research (v36 baseline)

This note distinguishes observations verified in the original Redline Rumble bytecode from ideas suggested by ZipZaps and Redline Rumble Revolution. Nothing from those other games has been merged into the v36 game.

## Verified original-game behaviour

In the original game's traffic script (LSCR resource **1509**):

- `beginSprite` chooses one road model (`mRoad`) through the Director world: one model for the earlier opponent selection and a second for the later one. The two branches meet at handler bytecode offset `0x013F`.
- At `exitFrame 0x0000–0x001D`, the game scrolls `mRoad.shaderList[1].textureTransform` to simulate road movement. This is distinct from constructing road tiles.
- A **30-entry same-direction traffic group list** (`gTrafficList`) is built and initially offset along Z by `-1000 * index` (beginSprite around `0x0757–0x07A7`).
- A separate **15-car oncoming traffic list** (`mTrafficList1`) is initialized with Z offsets `-2000 * index` (around `0x08B3–0x0987`).
- Real vehicles are selected from a pool and attached to traffic groups through traffic patterns/difficulty rules; the groups and car models are not interchangeable.
- In `exitFrame`, normal traffic is recycled when a group passes Z `+100` (`0x056D–0x0598`), using a `-30000` translation in the recycle path. Oncoming traffic has a `+200` recycle test (around `0x09D3–0x09E7`).
- The traffic script contains race-progress, opponent, collision and difficulty-dependent paths. Changing the recycle distance, group count or pool contents can indirectly change the race and should not be used as a quick draw-distance fix.

**Verified v35/v36 addition:** The separate rear visual copies are attached only to the scene graph. The original traffic simulation and recycle thresholds remain in place; user testing confirmed rear views retain passed cars.

## What the other games taught us

- **ZipZaps HQ:** Contains readable Lingo source, including vehicle, camera and controller implementations. This is a valuable syntax/architecture reference, not proof of shared traffic bytecode with the original Redline Rumble.
- **ZipZaps 2:** Its resource files may be closer to Redline Rumble historically. A complete structural script-by-script match has not yet been performed.
- **Redline Rumble Revolution:** Has named `CreateHighwayTile`, `BuildNextBlock`, `DeleteBlock`, `BuildTrafficOnBlock` and `UpdateTraffic` handlers. Its Director 11.5 block-based design is not directly compatible with the older Director game.

## Why the forward cars still pop in

The code confirms that real cars are recycled and populated at finite locations ahead. It does **not** yet prove whether the user's observed pop-in originates from:

1. A model being added to a traffic group or teleported to its forward position.
2. The car existing already but being culled by Director visibility bounds/LOD/fog.
3. The highway model ending before the camera's far clipping plane.

These may be different issues. Before altering traffic density or spawn timing, check which event corresponds to the pop-in seen in video.

## Experimental v37: road geometry only

Builder: [`experiments/build_rr_v37.py`](../experiments/build_rr_v37.py)

It multiplies `mRoad.transform.scale.z` by **4**, immediately after the road model is chosen, without replacing the model or modifying the traffic and camera handlers.

- Base: verified user-working v36 `game.dir` SHA-256 `771cbb57bb7ee6ef2c19ce23151dd9584e2a0995f90bd43a084237b50638c4ce`.
- Modified resource: LSCR **1509** (only its `beginSprite` code changes).
- Added: 21 bytes / ten instructions, with 41 original branch references rebased.
- All 1,599 other resource-map records unchanged.
- v36 camera resource 1506 unchanged.
- Traffic spawn, collision and recycling instructions remain unchanged.
- Current status: **static validation passed; Windows game test outstanding**.

This may reveal whether the road's finite geometry is responsible for the near horizon; it does **not** fix forward traffic pop-in. Scaling could alter UV appearance or produce seams, and should be reverted if rendering or race behaviour regresses.

## Testing checklist

1. Keep the original v36 installation to compare.
2. In each build, drive the same opponent/car/route and compare the *far road edge* in hood and chase views.
3. Inspect road markings/textures for stretching, swimming or mismatched geometry.
4. Verify `C` and hold/release `B` still work, passed cars remain visible, and the race can finish normally.
5. Check whether the forward car pop-in is unchanged (expected; no traffic code changed).
6. Record any verbose Director errors before clicking Continue.

Do not merge this experiment into `main` or publish a release until it passes a user gameplay test.
