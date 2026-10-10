# Technical notes

## Known-good development chain

`v22 → v28 (camera) → v35 (rear visual traffic) → v36 (camera restore)`

User reports confirm v36's camera behaviour and v35's visual rear traffic in the game. Static build reports alone do not prove runtime correctness on other PCs.

## Targeted Director resources

- **LSCR #1506** — camera controller. v36 changes this resource relative to v35.
- **LSCR #1509** — traffic controller. v35 modifies this resource while keeping other resource records unchanged.

Build scripts verify source hashes and the modified resource-map records, and compare untouched records byte-for-byte. These checks do not recreate the original Director editor project.

## Traffic retention vs gameplay traffic

Normal traffic is recycled ahead at the original logic thresholds (about +100 and +200 world units for the two traffic groups). v35 copies models for display behind the player just before that recycle. The visual copies are not inserted into AI, collision or race-progress lists.

This is why more cars remain visible behind the player while the normal traffic pool remains available ahead. It still requires in-game verification that long races do not hit Director-specific object limits.

**Do not simply extend recycling distances** to solve forward or rear pop-in. Earlier trials caused sparse traffic, collision issues and immediate race losses.

## Cameras

`C` toggles stock hood and distant chase. Holding `B` looks back. v36 moves the hood rear-view position beyond the player's vehicle model, then restores the saved position and original rotation operation on release.

Do not reintroduce experimental transform duplication or arbitrary rotation reads from broken v29-era builds without targeted runtime tests.

## Rendering limits

The original camera far-clipping distance was found to be approximately **999,900 world units**. That is not evidence that the actual road mesh or traffic models exist out to this distance.

Forward traffic pop-in may be linked to pool placement/recycling, while the road end may depend on geometry/tile generation. These should be investigated separately to preserve race difficulty.

## Audio

Unusual sound was observed/reported in third-person. Sound channel 3 has timed calls in the gameplay script, but their relationship to the reported noise was not established. No audio changes were included in v36.

## Runtime

The game uses legacy Macromedia Director/Shockwave 3D components. More capable hardware does not remove engine-specific model, script, resource or memory limitations. Keep verbose script error messages available during development.

## Testing standard

Do not mark a camera, traffic, or rendering change as fixed based on structural bytecode checks alone. Require an in-game test and distinguish static passing tests from user-confirmed gameplay results.