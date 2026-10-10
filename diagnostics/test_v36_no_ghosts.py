#!/usr/bin/env python3
"""Self-contained Director binary-layout regression tests; no game files required."""
from __future__ import annotations
import importlib.util
import struct
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('build_v36_no_ghosts.py')
spec = importlib.util.spec_from_file_location('rr_no_ghosts', SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def synthetic_movie(camera: bytes, traffic: bytes) -> bytes:
    movie = bytearray(b'XFIR' + b'\0' * (mod.MAP_START + mod.COUNT * mod.RECORD_SIZE - 4))
    for idx in range(mod.COUNT):
        struct.pack_into('<4sIIII', movie, mod.MAP_START + idx * mod.RECORD_SIZE,
                         b'eerf', 0, 0, 12, idx)
    for idx, data in ((mod.CAMERA_RESOURCE, camera), (mod.TRAFFIC_RESOURCE, traffic)):
        offset = len(movie)
        movie.extend(b'rcsL' + struct.pack('<I', len(data)) + data)
        struct.pack_into('<4sIIII', movie,
                         mod.MAP_START + idx * mod.RECORD_SIZE,
                         b'rcsL', len(data), offset, 0, 0)
    struct.pack_into('<I', movie, 4, len(movie) - 8)
    return bytes(movie)


class DirectorABTests(unittest.TestCase):
    def test_free_and_junk_records_are_not_active_resources(self):
        game = synthetic_movie(b'camera', b'traffic')
        self.assertIsNone(mod.resource(game, 1))
        self.assertEqual(mod.resource(game, mod.CAMERA_RESOURCE), b'camera')
        self.assertEqual(mod.resource(game, mod.TRAFFIC_RESOURCE), b'traffic')

    def test_reject_bad_resource_header(self):
        game = bytearray(synthetic_movie(b'camera', b'traffic'))
        _, _, off, _, _ = struct.unpack_from('<4sIIII', game,
            mod.MAP_START + mod.CAMERA_RESOURCE * mod.RECORD_SIZE)
        game[off] ^= 0x20
        with self.assertRaises(ValueError):
            mod.resource(bytes(game), mod.CAMERA_RESOURCE)

    def test_no_ghosts_preserves_new_camera_and_old_traffic(self):
        old = synthetic_movie(b'camera28', b'traffic28')
        new = synthetic_movie(b'camera36', b'traffic35')
        original28, original36 = mod.V28_SHA, mod.V36_SHA
        try:
            mod.V28_SHA, mod.V36_SHA = mod.sha(old), mod.sha(new)
            hybrid, report = mod.build(old, new)
        finally:
            mod.V28_SHA, mod.V36_SHA = original28, original36
        self.assertEqual(mod.resource(hybrid, mod.CAMERA_RESOURCE), b'camera36')
        self.assertEqual(mod.resource(hybrid, mod.TRAFFIC_RESOURCE), b'traffic28')
        self.assertEqual(report['changed_resources_relative_to_v36'], [mod.TRAFFIC_RESOURCE])
        self.assertEqual(report['changed_resources_relative_to_v28'], [mod.CAMERA_RESOURCE])

    def test_reject_unsupported_base_game_hash(self):
        a = synthetic_movie(b'oldcam', b'oldtraffic')
        b = synthetic_movie(b'newcam', b'newtraffic')
        with self.assertRaisesRegex(ValueError, 'hash'):
            mod.build(a, b)


if __name__ == '__main__':
    unittest.main()
