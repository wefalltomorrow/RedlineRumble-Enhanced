# v37 road experiment — native crash investigation

**Status:** v37 is unstable. Keep the experiment unmerged and retain v36 as the user-confirmed working baseline.

## Windows crash event

A `-CollectOnly` run of the diagnostic collector recovered the original Windows Application Error Event 1000 from **2026-10-10 16:48:43 local**.

| Item | Recorded value |
| --- | --- |
| Faulting application | `Projector.exe` 10.1.0.11 |
| Faulting module | `IML32.dll` 10.1.1.16 |
| Exception | `0xC0000005` (access violation) |
| Fault RVA | `0x00010CCD` |
| `Projector.exe` SHA-256 | `1b0a490e014044125febf056bbc9fab0b73f27ac6de193acf4cd6d4100eac549` |
| v37 `game.dir` SHA-256 | `58d4ec295f9c8c66edabd506ebf15a2ed22d442ac8ff0b60ac2c385887db5ed6` |

No full crash dump exists for the original incident; dump settings were enabled only after the crash. We therefore have **no call stack or register state**.

## Inspecting the actual runtime binary

Both v36 and v37 contain byte-identical `Iml32.dll` files:

`0ae5288fb41d9e58ad48600e6abe147bb7fe8ae850a490a3ec05fab9b9bd17e4`

The 32-bit PE preferred base is `0x69000000`; decoding its instructions at RVA `0x10CCD` gives:

```asm
69010cc8: test esi, esi
69010cca: push edi
69010ccb: je   0x69010d27
69010ccd: cmp  DWORD PTR [esi+4], 0x46415354
```

This is a dereference through a nonzero pointer (if control actually reached that instruction). A stale or invalid pointer is consistent with the access violation. **It is not possible to identify the owning object, underlying game operation or exact crash cause without a dump.** Do not treat the 4× road scaling as proven responsible merely because v37 introduced it.

## Verified game resource scope

The comparison of the extracted ZIPs confirms:

- Exactly one of the **1,600** Director resource payloads differs from v36: LSCR **1509**.
- Camera LSCR **1506** remains untouched.
- The original traffic `exitFrame` handler is unchanged; v37 adds **21 bytes** into `beginSprite` to scale `mRoad.transform.scale.z` by four.
- The existing rear-traffic visual hooks remain in LSCR 1509.
- The shipped executable and runtime DLLs match v36.

The binary modifications pass structural branch checks. Static validation cannot verify the renderer's stability over a full race.

### Traffic-controller state audit

In the original v28 controller, property 438 is named `mHighway` and is declared but not accessed by either of its two handlers. The working v35 rear-copy patch repurposes that controller property as a visual-model list. This is worth recording because it is not a newly created property, **but there is no evidence that this particular reuse caused v37's crash**. References via other objects have not been fully ruled out.

## What we need before another road build

1. Run the same full race in v36. If v36 also crashes, investigate the unbounded rear-copy accumulation as a separate possibility.
2. Repeat v37 only with the full diagnostic launcher if appropriate. Collect `MemoryUsage.csv`, application events and a WER/ProcDump `.dmp`.
3. Resolve the actual faulting pointer and call stack before changing the renderer again.
4. Keep forward traffic and road-horizon investigations independent; never change original traffic pools, collisions or difficulty as an unverified workaround.

The local audit utility (not bundled with the copyrighted game) can compare Director resource payloads logically rather than simply comparing whole-file hashes.

Related: experimental draft [PR #5](../pull/5), road draw-distance [Issue #2](../issues/2).
