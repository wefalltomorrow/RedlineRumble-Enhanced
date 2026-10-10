"""No-game-data regression checks for tools/audit_game_dir.py."""
import importlib.util
import struct
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'audit_game_dir.py'
spec = importlib.util.spec_from_file_location('rr_audit_game_dir', SCRIPT)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def sample_movie(payload):
    data = bytearray(b'\0' * (audit.MAP_OFFSET + audit.MAP_COUNT * audit.MAP_RECORD_SIZE))
    data[:4] = b'XFIR'
    for i in range(audit.MAP_COUNT):
        struct.pack_into('<4sIIII', data, audit.MAP_OFFSET + i * 20, b'eerf', 0, 0, 12, 4)
    offset = len(data)
    data.extend(b'tset' + struct.pack('<I', len(payload)) + payload)
    struct.pack_into('<4sIIII', data, audit.MAP_OFFSET, b'tset', len(payload), offset, 0, 0)
    struct.pack_into('<I', data, 4, len(data) - 8)
    return bytes(data)


class TestAudit(unittest.TestCase):
    def test_identical_resources(self):
        movie = sample_movie(b'hello')
        self.assertEqual(audit.resources(movie), audit.resources(movie))

    def test_resource_changes_not_position_changes(self):
        a = audit.resources(sample_movie(b'a'))
        b = audit.resources(sample_movie(b'b'))
        self.assertEqual([i for i, (x, y) in enumerate(zip(a, b)) if x != y], [0])

    def test_invalid_movie_size(self):
        data = bytearray(sample_movie(b'a'))
        struct.pack_into('<I', data, 4, 0)
        with self.assertRaisesRegex(ValueError, 'length mismatch'):
            audit.resources(bytes(data))

    def test_bad_chunk_header(self):
        data = bytearray(sample_movie(b'a'))
        data[-9:-5] = b'xxxx'
        with self.assertRaisesRegex(ValueError, 'chunk header'):
            audit.resources(bytes(data))

    def test_jump_alignment_valid(self):
        out = audit.decode(bytes.fromhex('41 01 53 02 01'))
        self.assertEqual(out['branch_count'], 1)

    def test_jump_alignment_invalid(self):
        with self.assertRaisesRegex(ValueError, 'Invalid Lingo jump'):
            audit.decode(bytes.fromhex('41 01 53 01 01'))


if __name__ == '__main__':
    unittest.main()
