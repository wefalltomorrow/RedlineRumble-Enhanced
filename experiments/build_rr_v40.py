#!/usr/bin/env python3
"""v40 experimental pooled rear traffic: reuse 32 existing scene models without model deletion.

Once 32 visual clones exist, the oldest model is updated with the new car's resource, shader and world transform; no additional models are created.
Requires the hash-verified v28/v36 game ZIPs owned by the user.
No original game/runtime files are kept in this repository.
Static validation does NOT establish crash-free gameplay.
"""
from __future__ import annotations
import argparse
from copy import copy
import hashlib
import json
import struct
import zipfile
from pathlib import Path
import sys

LIMIT = 32
V28 = "063733277ca3e2a37334fa2c1a9ebfaa310675d5d19a1ded2551b8cf803874d4"
V36 = "771cbb57bb7ee6ef2c19ce23151dd9584e2a0995f90bd43a084237b50638c4ce"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pooled_clone(v35, original_emitter, b, oncoming: bool):
    """Fixed pool: reuse oldest 3D model at count 32; NEVER delete a 3D model.

    This is a Director runtime experiment. Geometry/shader/transform setters
    have not been tested in-game. List.deleteAt removes only the list slot.
    """
    v35.push(b, LIMIT)
    v35.prop(b, 438)
    v35.getobj(b, 66)
    b.emit(0x0d)             # LIMIT <= mHighway.count
    b.jmp(0x55, "new_clone")  # Under the cap -> original v35 clone routine.

    v35.prop(b, 438)
    v35.push(b, 1)
    v35.argret(b, 2)
    v35.call(b, 65)          # oldest = mHighway.getAt(1)
    v35.setloc(b, 1)

    for propid in (448, 158, 106, 105):  # resource, shaderList, transform, worldPosition
        v35.loc(b, 1)        # old model to update
        if oncoming:
            v35.model_from_oncoming(b)
        else:
            v35.model_from_group_child(b)
        v35.chained(b, propid)
        v35.setobj(b, propid)

    v35.prop(b, 438)
    v35.push(b, 1)
    v35.args(b, 2)
    v35.call(b, 432)         # list.deleteAt(1), not W.deleteModel!
    v35.prop(b, 438)
    v35.loc(b, 1)
    v35.args(b, 2)
    v35.call(b, 78)          # list.add(reusedModel)
    b.jmp(0x53, "done")

    b.label("new_clone")
    original_emitter(b, oncoming)
    b.label("done")


def build(v35, v28: bytes, v36: bytes):
    if sha(v28) != V28 or sha(v36) != V36:
        raise ValueError("Wrong v28/v36 game.dir hash; refusing to patch")
    original = v35.resource(v28, 1509)
    source = v35.create_one_visual
    try:
        v35.create_one_visual = lambda b, oncoming: pooled_clone(v35, source, b, oncoming)
        changed, patch_report = v35.rewrite(original)
    finally:
        v35.create_one_visual = source

    game = bytearray(v36)
    offset = len(game)
    game.extend(b"rcsL" + struct.pack("<I", len(changed)) + changed)
    struct.pack_into("<II", game, v35.MAP + 1509*v35.REC_SZ + 4, len(changed), offset)
    struct.pack_into("<I", game, 4, len(game)-8)
    output = bytes(game)

    assert v35.resource(output, 1509) == changed
    assert v35.resource(output, 1506) == v35.resource(v36, 1506)
    # All original bytes apart from global size and resource 1509 map are
    # unchanged. The preexisting resource payloads stay at the same offsets.
    rec = v35.MAP + 1509*v35.REC_SZ
    assert output[:4] == v36[:4]
    assert output[8:rec] == v36[8:rec]
    assert output[rec+v35.REC_SZ:len(v36)] == v36[rec+v35.REC_SZ:]
    for i in range(v35.N):
        if i != 1509:
            p = v35.MAP + i*v35.REC_SZ
            assert output[p:p+v35.REC_SZ] == v36[p:p+v35.REC_SZ], i
    # Stable comparison target from direct local bytecode build against hash-checked inputs.
    EXPECTED_V40_GAME_SHA = "7d3038fcdea01d85f741f31f023075a8a6ad28175291f5c46e1033f65f73a056"
    assert sha(output) == EXPECTED_V40_GAME_SHA, (
        "GitHub v40 source drifted from locally validated bytecode image", sha(output)
    )
    patch_report.update({
        "status": "STATIC VALIDATION PASSED; WINDOWS PLAYTEST PENDING",
        "source_v28_sha256": sha(v28),
        "source_v36_sha256": sha(v36),
        "output_game_sha256": sha(output),
        "changed_resource_relative_to_v36": [1509],
        "camera_1506_unchanged": True,
        "visual_clone_limit": LIMIT,
        "ghost_removal": "None: model identity retained; list reference rotated",
        "delete_model_and_reuse_names": False,
        "pool_reuse": "copy resource/shaderList/transform/worldPosition into existing model",
        "runtime_stability_verified": False,
    })
    return output, patch_report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v28", type=Path, required=True)
    p.add_argument("--v36", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("RR_v40_PooledGhosts_Experimental.zip"))
    a = p.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))
    import build_redline_v35 as v35
    with zipfile.ZipFile(a.v28) as old, zipfile.ZipFile(a.v36) as new:
        assert old.testzip() is None and new.testzip() is None
        game, report = build(v35, old.read("game.dir"), new.read("game.dir"))
        notes = (
            "Redline Rumble v40 — Hard-Cap Rear Ghosts (DIAGNOSTIC)\n\n"
            "Based on the v36 camera build, with a maximum 32 visual rear cars.\n"
            "No deleteModel or 3D name reuse: at the cap, updates the oldest clone.\n"
            "The original traffic simulation, difficulty and collisions are intact.\n"
            "Director mesh/transform setters are experimental; may crash or display incorrectly.\n"
            "Not yet tested in a full Windows race; may still crash.\n"
            "Run the same race that crashed in v36 and send logs if needed.\n"
        )
        with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as dst:
            for entry in new.infolist():
                if entry.filename == "README v36.txt":
                    continue
                dst.writestr(copy(entry), game if entry.filename == "game.dir" else new.read(entry.filename))
            dst.writestr("README v38.txt", notes)
        with zipfile.ZipFile(a.out) as check:
            assert check.testzip() is None
            assert check.read("game.dir") == game
            for name in set(new.namelist()) - {"game.dir", "README v36.txt"}:
                assert check.read(name) == new.read(name), name
    report["output_zip_sha256"] = sha(a.out.read_bytes())
    audit = a.out.with_name("RR_v40_Validation.json")
    audit.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Report:", audit)


if __name__ == "__main__":
    main()
