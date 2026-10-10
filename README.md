# Redline Rumble Enhanced

An unofficial enhancement project for **Redline Rumble**, the classic Shockwave racing game.

The aim is to make the game more enjoyable on modern PCs without changing the original race balance.

## Current state

**v36 is the latest player-tested working build.** This is a development baseline, not a published GitHub Release.

- Native 4K / widescreen fullscreen rendering (existing experimental patches)
- 60 FPS timing modifications and graphics configuration
- `C` switches between hood view and a third-person chase camera
- Hold `B` to look backwards; releasing restores the selected camera
- Hood rear-view camera is positioned behind the car rather than inside its bodywork
- Passed traffic remains visible behind the player using visual-only copies
- Original forward traffic recycling thresholds, spacing logic and near-player collision logic are retained

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

See [building instructions](docs/building.md) to reproduce the development build locally. Publicly redistributable patch bundles and a GitHub Release are planned but **not published yet**.

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