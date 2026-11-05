# Continuation checkpoint — 25 October 2026

## Evidence and baseline

Recovered the supplied continued-conversation export and its 97 files, including
the earlier conversation archive, game builds, source scripts, screenshots,
recording, crash logs and related-game research. The original export and binary
attachments remain local; they are not part of this public repository.

Fetched main and all seven investigation/experiment branches. Main was still
`8a0014ea823ac208db9604c4e74081f8cdd2d4b6`. Reviewed open issues, experimental
PR discussions and Actions results. No v41 gameplay result was present.

| Build | User-observed result | Interpretation |
| --- | --- | --- |
| v28 | Working camera baseline | Pre-cloning development baseline; hood rear return needs repair |
| v35 | Rear visuals worked | Unlimited clones; not a full-race stability result |
| v36 | Cameras worked, later race crash | Camera baseline only |
| v37 | Native access violation in IML32.dll | Road scaling cannot alone explain shared v36 crash |
| v36 NoGhosts | User said the build did not crash | Historical assistant strengthened this to same-race completion; scope is less explicit than v39 |
| v38 | Crashed | Deleting/recreating clones did not solve the problem |
| v39 | Race, victory and menu completed | Latest full-race-confirmed reference; stops after 32 clones |
| v40 | Director `Property not found: #shaderList` | Script error; not a recorded native crash |
| v41 | No gameplay result supplied | Reproduced exactly; runtime behavior unknown |
| v42 | No gameplay result yet | Eleven local-operand bytes corrected on v39; cap retained |

The green truck and checkered flag at victory are normal. One successful race
does not establish stability across repeated races. Original recycling remains
at +100/+200 with the -30000 translation and original AI/collision lists.
These are comparisons to the inherited development baseline. Earlier timing
and pool experiments mean original-2003 difficulty equivalence is not proven.
The user had explicitly expressed uncertainty about traffic equivalence.

All four relevant recovered Redline transcripts were read in full, including
older assistant narratives (364 messages, including overlapping exports).
This does not mean every binary, historical screenshot or video was reviewed.
Some older referenced attachments are absent; all continuation links resolve.
The early fullscreen performance problem was attributed by the user to a
Bandicam/RTSS interaction; preserve that correction to the earlier diagnosis.
Game preferences are shared under AppData, so separate build folders do not
provide separate save files.

## Reproduction and source comparison

Rebuilt v35, v36, v38, v39, v40 and v41 game data from their respective GitHub branches
using recovered inputs. All six were byte-for-byte identical to the
archived game data. ZIP wrapper metadata can differ.

| Build | game.dir SHA-256 |
| --- | --- |
| v28 | `063733277ca3e2a37334fa2c1a9ebfaa310675d5d19a1ded2551b8cf803874d4` |
| v36 | `771cbb57bb7ee6ef2c19ce23151dd9584e2a0995f90bd43a084237b50638c4ce` |
| v38 | `329d95cda176a651b6c868ce66e20301b3fca88b53ab988b2a66734b2c87a119` |
| v39 | `73b5bc4e2e57e35abc839eb1a1152d88cb7405be60ee9a7ab7b0748be5a375b5` |
| v40 | `7d3038fcdea01d85f741f31f023075a8a6ad28175291f5c46e1033f65f73a056` |
| v41 | `e0e3542f4c95f17ddcc37c854ed1a3acda4cefefab112710ba11150c581d0c7a` |

Archived v35 source and GitHub source have identical Python ASTs. v28 and v36
differences concern paths/documentation, with camera/traffic generation functions
unchanged. v35/v36 test differences concern import paths. The v41 repository
builder is reorganized relative to the attachment, but reproduces the exact
archived game bytes. Preserve historical builders for reproduction.

## Latest API audit

The decisive finding is an incorrect historical local-variable rule. The
original traffic exitFrame declares three locals and uses operands 0,1,2.
The injected v35-v41 paths use 8 and 16. The 46-byte handler layout and
ProjectorRays' version-dependent decoder support direct indices for this
movie. Historical comments claiming slot*8 remain preserved for exact
reproduction, but must not guide new patches. [v42](v42-local-indices.md)
isolates the eleven affected operands on the successful v39 reference.

The original Macromedia Lingo Dictionary documents `worldPosition` as get-only
(p. 730). v41 still attempts to set it, but the original movie also contains
worldPosition setter instructions (including traffic initialization). That
contradiction prevents concluding from the manual alone that the runtime
cannot support the assignment. `shaderList` is a documented model
property (p. 599); the v40 error does not show that Director lacks the API.
The direct shaderList setter is documented for a shader reference broadcast,
not an arbitrary source-list replacement. `transform` is parent-relative.
Original scripts also assign resource. The setter pops value then target;
the v40/v41 setter order is not reversed. ProjectorRays models both 0x61 and
0x70 getters as consuming the receiver; there is no support for treating
0x70 as a peek. Native reference/value distinctions remain unresolved.

v41's shared oldest-model pool can reuse a clone across traffic directions
without updating its parent. Same-direction cars originate inside a group
under parent401, while oncoming cars are directly under parent402. Copying
local transforms across these parents is not a reliable world-space move.
This is a separate defect from the out-of-range locals and the shader error.
v43 now investigates separate direction pools and world-space delta translation
as an isolated diagnostic. v42 gameplay results are still needed for comparison;
the user authorized continued implementation while those results are pending.

Primary manuals:

- [worldPosition](https://www.manualslib.com/manual/389805/Macromedia-Director-Mx-Lingo-Dictionary.html?page=730)
- [shaderList](https://www.manualslib.com/manual/389805/Macromedia-Director-Mx-Lingo-Dictionary.html?page=599)
- [Model/node properties](https://www.manualslib.com/manual/389802/Macromedia-Director-Mx-2004-Using-Director.html?page=347)

The inherited v41 validation field `no_extra_worldPosition_assignment: true`
is misleading: it comes from v35 although v41 adds that setter. Its old report
and static opcode-count tests do not validate property types or runtime safety.

## Remaining gates

Every diagnostic needs a Windows gameplay result beyond pool saturation, then
finish/victory/menu and another race without restarting. Do not merge an
untested experiment. Forward pop-in, road length, chase audio, repeated-race
lifetime and patch-only release packaging remain open; no changes to these
systems are justified by the current clone-reuse investigation alone.

v42 now passes twelve source-only tests, the five existing v41 tests, v36 camera
regression checks, six resource-auditor tests and Python syntax compilation.
An independent binary review matched the eleven-byte correction exactly.
All other 1,599 mapped resources and other packaged payloads are unchanged.
No native gameplay test was performed; v42 is not a stability claim.

## November 5: v43 engineering milestone

The continuous-reuse diagnostic is implemented on `experiment/v43-directional-reuse`.
See [its scope, reproducible build and validation limits](v43-directional-reuse.md).
The two pools prevent cross-direction parent mismatches; world-space translation
avoids source subgroup reparenting and all model property setters on reuse.
Retained appearance/rotation/scale is an intentional diagnostic limitation.
The 10,000-event synthetic bytecode test is automated evidence, not gameplay.
Do not merge or label this stable before native full-race and second-race results.
