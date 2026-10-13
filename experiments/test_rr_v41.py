#!/usr/bin/env python3
"""Source-only static tests; no original game assets required."""
from pathlib import Path
import importlib.util, unittest

root=Path(__file__).resolve().parents[1]
def load(label, path):
    spec=importlib.util.spec_from_file_location(label,path)
    assert spec and spec.loader
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

v35=load('rr_v35',root/'source'/'build_redline_v35.py')
v41=load('rr_v41',root/'experiments'/'build_rr_v41.py')

class ReuseChecks(unittest.TestCase):
    def test_exact_removed_property(self):
        self.assertEqual(v41.V40_PROPS,(448,158,106,105))
        self.assertEqual(v41.V41_PROPS,(448,106,105))
        self.assertEqual(v41.LIMIT,32)

    def test_both_directions_no_shaderlist_access(self):
        for oncoming in (False, True):
            with self.subTest(oncoming=oncoming):
                b=v35.Seq()
                v41.pooled_clone(v35,v35.create_one_visual,b,oncoming,v41.V41_PROPS)
                ins=v35.decode(b.resolved(),allow_end=True)
                self.assertFalse(any(x['op'] in (0x70,0x62) and x['val']==158 for x in ins))
                for propid in v41.V41_PROPS:
                    for opcode in (0x70,0x62):
                        self.assertEqual(sum(x['op']==opcode and x['val']==propid for x in ins),1)

    def test_original_v40_includes_faulting_access(self):
        b=v35.Seq()
        v41.pooled_clone(v35,v35.create_one_visual,b,False,v41.V40_PROPS)
        ins=v35.decode(b.resolved(),allow_end=True)
        self.assertTrue(any(x['op']==0x70 and x['val']==158 for x in ins))
        self.assertTrue(any(x['op']==0x62 and x['val']==158 for x in ins))

    def test_no_model_delete(self):
        b=v35.Seq()
        v41.pooled_clone(v35,v35.create_one_visual,b,False,v41.V41_PROPS)
        ins=v35.decode(b.resolved(),allow_end=True)
        calls=[x['val'] for x in ins if x['op']==0x67]
        self.assertNotIn(397,calls)  # W.deleteModel
        self.assertIn(432,calls)     # list.deleteAt only

    def test_hash_guard(self):
        self.assertEqual(len(v41.EXPECTED_V40_GAME_SHA),64)
        self.assertEqual(len(v41.EXPECTED_V41_GAME_SHA),64)
        self.assertNotEqual(v41.EXPECTED_V40_GAME_SHA,v41.EXPECTED_V41_GAME_SHA)

if __name__=='__main__':
    unittest.main()
