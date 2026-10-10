#!/usr/bin/env python3
"""Regression tests for v39's deletion-free cap. No game files required."""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

v35 = load('redline_v35_test', ROOT / 'source' / 'build_redline_v35.py')
v39 = load('redline_v39_test', ROOT / 'experiments' / 'build_rr_v39.py')

class HardCapTests(unittest.TestCase):
    def test_total_limit(self):
        self.assertEqual(v39.LIMIT, 32)

    def test_both_hook_directions_have_valid_control_flow(self):
        for from_oncoming in (False, True):
            with self.subTest(from_oncoming=from_oncoming):
                seq = v35.Seq()
                v39.bounded_clone(v35, v35.create_one_visual, seq, from_oncoming)
                ins = v35.decode(seq.resolved(), allow_end=True)
                calls = [x['val'] for x in ins if x['op'] == 0x67]
                for method in (153, 316, 78):
                    self.assertEqual(calls.count(method), 1)
                for method in (397, 432):
                    self.assertNotIn(method, calls)
                self.assertEqual(sum(x['op'] == 0x55 for x in ins), 1)
                self.assertEqual(sum(x['op'] == 0x53 for x in ins), 1)
                self.assertEqual(ins[0]['op'], 0x41)
                self.assertEqual(ins[0]['val'], 32)

    def test_source_emitter_unchanged(self):
        before = v35.create_one_visual
        with self.assertRaises(Exception):
            v35.rewrite(b'bad')  # not part of the patch, just input safety
        self.assertIs(v35.create_one_visual, before)

if __name__ == '__main__':
    unittest.main()
