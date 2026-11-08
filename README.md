# Redline Rumble Enhanced

An unofficial enhancement project for **Redline Rumble**, the classic Shockwave racing game.

The aim is to make the game more enjoyable on modern PCs without changing the original race balance.

## Current state

**v39 is the latest build confirmed by the player to complete a full race, victory screen and return to menu.** Its visual rear traffic stops growing after 32 clones. v36 remains the camera baseline, but its unlimited clones were followed by a race crash. No stable GitHub Release has been published.

v40 failed with a Director `#shaderList` script error. v41 has no supplied gameplay result. See the [continuation checkpoint](docs/continuation-2026-10-25.md) for reproduced hashes, evidence and unresolved questions.

**v42 is a gameplay-unverified diagnostic based on v39.** It corrects eleven out-of-range traffic-local operands, using the original handler's direct indices. It retains the 32-clone cap so this correction can be tested separately before attempting continuous model reuse. See [v42 evidence and build instructions](docs/v42-local-indices.md).

**v43 adds an isolated continuous-reuse diagnostic.** It uses two 16-model pools and world-space translation to keep updating rear traffic after saturation, retaining each clone's appearance and orientation. Automated bytecode tests pass; native gameplay and repeated-race cleanup remain unverified. See [v43 build and test instructions](docs/v43-directional-reuse.md). v42 remains available for the first comparison playtest.

- Native 4K / widescreen fullscreen rendering (existing experimental patches)
- 60 FPS timing modifications and graphics configuration
- `C` switches between hood view and a third-person chase camera
- Hold `B` to look backwards; releasing restores the selected camera
- Hood rear-view camera is positioned behind the car rather than inside its bodywork
- Passed traffic remains visible behind the player using visual-only copies
- Forward traffic recycling and gameplay logic are retained relative to the v28 development baseline; equivalence to the original 2003 difficulty has not been established

**Still being investigated:** forward traffic pop-in, road/environment draw distance, and unusual audio in chase view. Runtime behaviour depends on the specific Director/Windows setup.

## Repository contents

- [`source/`](source/) — Python build/bytecode patch scripts for v28 → v35 → v36
- [`tests/`](tests/) — static checks, including camera input-state simulation
- [`docs/building.md`](docs/building.md) — input requirements and build sequence
- [`docs/technical-notes.md`](docs/technical-notes.md) — patched script resources and known limitations
- [`CHANGELOG.md`](CHANGELOG.md) — development history

These are **patch-building tools**, not a decompilation or the original game's complete source code.

## Builds and installation

No downloadable game executable is included in this repository. Macromedia Director runtime components, the original game, and third-party graphics DLLs belong to their respective owners. The build scripts expect specific historical game snapshots supplied by the user, verified against SHA-256 checks to prevent accidentally patching the wrong version.

See [building instructions](docs/building.md) to reproduce the development build locally. The [source-only diagnostic comparison kit](diagnostics/README.md) installs the exact v42/v43 payloads from user-owned historical ZIPs, checking every input and output file. A stable GitHub Release has **not** been published.

The kit also includes a native-session recorder for manually launched v42/v43
playtests: process exits, memory samples, loaded module paths and matching
Windows events are saved locally. It does not change game behavior or system
dump settings, and never treats an exit code as proof of a completed race.

## Controls

| Key | Action |
| --- | --- |
| `C` | Toggle hood / third-person chase view |
| Hold `B` | Look backwards |
| Release `B` | Return to selected view |

## Roadmap

Track upcoming changes under [Issues](../../issues). The main goals are to reduce forward traffic pop-in, extend the road horizon and investigate chase-view audio without affecting the original traffic difficulty.

## Credits

Enhancements and patch scripts developed as an unofficial community project. Redline Rumble and the original game assets are the property of their respective owners. This project is not affiliated with or endorsed by the original developer, publisher, Adobe, or Macromedia.

No license has yet been assigned to this repository's original scripts.
