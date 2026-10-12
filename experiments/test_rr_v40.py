#!/usr/bin/env python3
"""Source-only v40 hook validation; not a Director runtime test."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source'))
sys.path.insert(0, str(ROOT / 'experiments'))
import build_redline_v35 as v35
import build_rr_v40 as v40

class PoolTests(unittest.TestCase):
    def test_limit(self):
        self.assertEqual(v40.LIMIT, 32)

    def test_reuse_and_creation_paths_both_present(self):
        for oncoming in (False, True):
            with self.subTest(oncoming=oncoming):
                s = v35.Seq()
                v40.pooled_clone(v35, v35.create_one_visual, s, oncoming)
                ins = v35.decode(s.resolved(), allow_end=True)
                calls = [x['val'] for x in ins if x['op'] == 0x67]
                setters = [x['val'] for x in ins if x['op'] == 0x62]
                getters = [x['val'] for x in ins if x['op'] == 0x70]
                self.assertEqual((ins[0]['op'], ins[0]['val']), (0x41, 32))
                self.assertEqual(sum(x['op'] == 0x55 for x in ins), 1)
                self.assertEqual(calls.count(153), 1) # clone only on < 32 branch
                self.assertEqual(calls.count(316), 1) # addChild only on < 32
                self.assertEqual(calls.count(65), 6)  # 1 oldest + 4 source-property reads + 1 creation path
                self.assertEqual(calls.count(432), 1) # only list.deleteAt(1)
                self.assertEqual(calls.count(78), 2)  # list.add, either path
                self.assertNotIn(397, calls)  # W.deleteModel is absent
                for prop in (448, 158, 106, 105):
                    self.assertEqual(setters.count(prop), 1)
                    self.assertEqual(getters.count(prop), 1)
                self.assertEqual(s.labels['done'], len(s.buf))

    def test_metadata_has_no_game_binaries(self):
        self.assertFalse((ROOT / 'experiments' / 'RR_v40_PooledGhosts_Experimental.zip').exists())

if __name__ == '__main__':
    unittest.main(verbosity=2)
