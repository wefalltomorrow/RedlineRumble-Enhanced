#!/usr/bin/env python3
"""Static tests for v38 bytecode; no original game files required."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_redline_v35 as v35
import build_rr_v38 as v38


class CloneCleanupTests(unittest.TestCase):
    def test_cap(self):
        self.assertEqual(v38.LIMIT, 32)

    def test_bytecode_both_directions(self):
        for is_oncoming in (False, True):
            with self.subTest(is_oncoming=is_oncoming):
                b = v35.Seq()
                v38.bounded_clone(v35, b, is_oncoming)
                instructions = v35.decode(b.resolved(), allow_end=True)
                calls = [op["val"] for op in instructions if op["op"] == 0x67]
                for call in [397, 432, 153, 316, 78]:
                    self.assertEqual(calls.count(call), 1, call)
                # Delete old *scene model*, release old list reference, then clone.
                self.assertLess(calls.index(397), calls.index(432))
                self.assertLess(calls.index(432), calls.index(153))
                self.assertLess(calls.index(153), calls.index(316))
                self.assertLess(calls.index(316), calls.index(78))
                self.assertTrue(any(op["op"] == 0x61 and op["val"] == 190
                                    for op in instructions))  # model.name
                self.assertTrue(any(op["op"] == 0x41 and op["val"] == 32
                                    for op in instructions))
                self.assertEqual(sum(op["op"] == 0x55 for op in instructions), 1)
                self.assertEqual(sum(op["op"] == 0x53 for op in instructions), 1)
                self.assertTrue(all(op["op"] != 0x4c or op["val"] in (0,8,16)
                                    for op in instructions))

    def test_hooks_resolve(self):
        original = v35.create_one_visual
        try:
            v35.create_one_visual = lambda seq, oncoming: v38.bounded_clone(v35, seq, oncoming)
            v35.decode(v35.ongoing_hook(), allow_end=True)
            v35.decode(v35.oncoming_hook(), allow_end=True)
        finally:
            v35.create_one_visual = original

    def test_expected_fixed_symbol_numbers(self):
        self.assertEqual(v35.INDEX, 1509)
        self.assertEqual(v35.MAP, 136)


if __name__ == "__main__":
    unittest.main()
