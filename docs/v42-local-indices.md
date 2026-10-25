# v42: local-index diagnostic on v39

The rear-traffic patches access local slots outside the traffic handler's
declared table. v42 corrects exactly eleven operand bytes in v39, preserving
its 32-clone cap and no-delete behavior. Gameplay remains unverified.
Continuous reuse is deferred until this prerequisite has an in-game result.

## Evidence

Lscr1509 exitFrame declares three locals: i, tempRand, j. Original accesses
use direct indices 0,1,2. Initialization declares eighteen locals and uses
0 through17, independently confirming the encoding. The 46-byte handler
records include stackHeight at record+42. ProjectorRays uses this field for
format versions >=850 and a local multiplier of1; multiplier8 applies to
older formats. The handoff's blanket slot*8 rule was incorrect for this movie.

- [Pinned handler reader and variableMultiplier implementation](https://github.com/ProjectorRays/ProjectorRays/blob/6f9bcebf626b43719abe2affcbbcb041d154d666/src/lingodec/handler.cpp#L26)
- [Pinned local decoder](https://github.com/ProjectorRays/ProjectorRays/blob/6f9bcebf626b43719abe2affcbbcb041d154d666/src/lingodec/handler.cpp#L145)

Six operands change 8 to1; five change16 to2. Instruction offsets relative
to exitFrame are 0x582,0x584,0x5b4,0x5cd,0x5d2,0x5df,0x5e7,0x5ea,
0xa80,0xa85,0xa92. The changed byte is at instruction offset+1.
Initialization's valid indices8/16 are untouched.

This proves a static operand defect, not the mechanism of the IML32 crash
or the exact receiver causing v40's shaderList error. v39's successful race
does not invalidate the bytecode finding or establish native runtime safety.

## Validation and limits

The hash-guarded builder rejects other input movies and existing output ZIPs.
It checks every branch and unchanged instruction, exact edit sites, resource
identity, package payload identity and scratch-local liveness across branches
and loops. The same-direction hook occupies [0x580,0x5ef); the oncoming hook
occupies [0xa56,0xa98). Local0 remains the original traffic index. Locals1/2
are not read after the hook before a subsequent write or handler return.

The hook stack checker reports a relative peak of4. Independent whole-handler
analysis found one value at each hook entry, so the absolute hook peak is5;
the full handler peaks at7, matching its unchanged declaration. Initialization
retains18. The small hook checker alone does not prove whole-handler stack
safety; the independent analysis and exact hash lock bound this conclusion
to this candidate.

Eight source-only tests execute both hooks in a strict three-local model,
reject the old out-of-range accesses, exercise cap crossing and repeated
calls after saturation, and test liveness/stack validation failures. Five
existing v41 tests, the v36 camera suite, six resource-auditor tests and
Python syntax compilation pass. These models do not execute Director.

Binary validation finds only resource1509 changed; all other1,599 resources
are identical. The entire movie differs by exactly11 bytes. Cameras,
fullscreen helper, runtime, assets and all other packaged payloads are
preserved; only the current README is replaced.

## Reproduce

Use a user-owned exact v39 ZIP and a new output path:

```powershell
python experiments/build_rr_v42.py --v39 C:/path/RR_v39_HardCap32.zip --out C:/path/RR_v42_LocalIndices_Diagnostic.zip
python experiments/test_rr_v42.py -v
python tools/audit_game_dir.py C:/path/RR_v39_HardCap32.zip C:/path/RR_v42_LocalIndices_Diagnostic.zip --output C:/path/audit.json
```

The complete historical build_rr_v39.py was copied byte-for-byte from
experiment/v39-hardcap-no-delete at9658e3c. Its README v38 filename is an
existing packaging typo preserved for reproduction. The v42 builder imports
the existing v35 decoder; it does not execute that builder's old local emitter.

| Artifact | SHA-256 |
| --- | --- |
| Input v39 game.dir | `73b5bc4e2e57e35abc839eb1a1152d88cb7405be60ee9a7ab7b0748be5a375b5` |
| Output v42 game.dir | `b78e407798a1f7fbd32c7bae647572ace73fb5542de0ca11e0444024076d72bd` |
| Local diagnostic ZIP | `cf1c975c7d1cf27516bc5c9d00076256013202d7aae91efd729c0aca639a125f` |

The ZIP hash describes this packaged baseline and compression environment;
movie-byte equality is the portable reproduction check. Proprietary game
and runtime files are not committed or attached to the public PR.

## Gameplay gate

Extract into a new folder and run its existing launcher. Use the race/car
that succeeded on v39 and failed on earlier builds. Check the first rear
visuals, both traffic directions, B rear-view and C hood/chase transitions.
Complete the race, victory screen and menu, then start another race without
restarting the game. Compare fullscreen/4K, performance, traffic and
collision behavior against v39. Green truck/checkered flag are normal.

Record race/car, elapsed time, whether initial rear visuals appeared,
full-race and second-race results, and exact Director error or crash-log
details if it fails. Separate folders still share the AppData save file.

This build intentionally stops adding rear visuals at32. Neither continuous
retention, original-2003 difficulty equivalence nor repeated-race stability
is claimed. Keep this PR draft and unmerged pending gameplay evidence.
