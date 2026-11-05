#!/usr/bin/env python3
"""Execute emitted hooks in a strict synthetic VM, not the Director runtime."""
import random
import unittest
import build_rr_v43 as build

class Vec(tuple):
    def __add__(self, other):
        return Vec(a+b for a, b in zip(self, other))
    def __sub__(self, other):
        return Vec(a-b for a, b in zip(self, other))

class Node:
    def __init__(self, name, parent=None, pos=(0, 0), turns=0, scale=1):
        self.name, self.parent, self.pos = name, parent, Vec(pos)
        self.turns, self.scale, self.children = turns, scale, []
        self.appearance = name
        if parent is not None:
            parent.children.append(self)
    def apply(self, p):
        x, y = p
        for _ in range(self.turns % 4):
            x, y = -y, x
        return Vec((x*self.scale, y*self.scale)) + self.pos
    def unapply(self, p):
        x, y = p-self.pos
        x, y = x/self.scale, y/self.scale
        for _ in range((-self.turns) % 4):
            x, y = -y, x
        return Vec((x, y))
    def to_world(self, p):
        p = self.apply(p)
        return self.parent.to_world(p) if self.parent else p
    def from_world(self, p):
        return self.unapply(self.parent.from_world(p) if self.parent else p)
    @property
    def world(self):
        return self.parent.to_world(self.pos) if self.parent else self.pos
    def place(self, world):
        self.pos = self.parent.from_world(world) if self.parent else world

class VM:
    def __init__(self):
        self.m = build.emitter()
        self.same = Node('same', pos=(1000, -400), turns=1, scale=2)
        self.opposite = Node('opposite', pos=(-200, 300), turns=3, scale=4)
        self.group = Node('group', self.same, (25, 31), turns=2, scale=2)
        self.sources = [Node('carA', self.group, (2, 9)), Node('carB', self.group, (-3, 5))]
        self.oncoming = Node('truck', self.opposite, (-10, 20))
        self.props = {401:self.same, 402:self.opposite, 403:[self.group], 386:[self.oncoming]}
        self.locals = [1, None, None]
        self.created, self.translated = [], []
        self.run(build.initialize(self.m), caller=False)

    def call(self, method, args):
        obj, *params = args
        if method == 65:
            index, = params
            if not 1 <= index <= len(obj):
                raise AssertionError('Invalid 1-based list access')
            return obj[index-1]
        if method == 36:
            kind, index = params
            assert kind == 434
            return obj.children[index-1]
        if method == 66:
            assert params == [434]
            return len(obj.children)
        if method == 153:
            name, = params
            assert name not in [n.name for n in self.created]
            clone = Node(name, obj.parent, obj.pos, obj.turns, obj.scale)
            clone.appearance = obj.appearance
            self.created.append(clone)
            return clone
        if method == 316:
            child, mode = params
            assert mode == 436
            world = child.world
            child.parent.children.remove(child)
            child.parent = obj; obj.children.append(child); child.place(world)
        elif method == 78:
            value, = params; obj.append(value)
        elif method == 432:
            index, = params; del obj[index-1]
        elif method == build.TRANSLATE:
            delta, space = params
            assert space == build.WORLD and isinstance(delta, Vec)
            obj.place(obj.world+delta); self.translated.append(obj)
        else:
            raise AssertionError(('Unexpected method', method))

    def run(self, code, caller=True):
        ins = {i['s']: i for i in self.m.decode(code, allow_end=True)}
        sentinel = object(); stack = [sentinel] if caller else []
        pc, steps = 0, 0
        while pc != len(code):
            steps += 1
            assert steps < 100000, 'Hook failed to terminate'
            i = ins[pc]; op, val = i['op'], i['val']; pc = i['e']
            if op == 0x41: stack.append(val)
            elif op == 0x44: stack.append({11:'rear', 14:'copy'}[val])
            elif op == 0x45: stack.append(val)
            elif op == 0x4a: stack.append(self.props[val])
            elif op == 0x50: self.props[val] = stack.pop()
            elif op == 0x4c: stack.append(self.locals[val])
            elif op == 0x52: self.locals[val] = stack.pop()
            elif op in (0x42, 0x43): stack.append((val, op == 0x43))
            elif op in (0x67, 0x1e):
                count, returning = stack.pop()
                args = stack[-count:] if count else []
                if count: del stack[-count:]
                result = list(args) if op == 0x1e else self.call(val, args)
                if returning: stack.append(result)
            elif op == 0x61:
                obj = stack.pop()
                if val == 66: stack.append(len(obj))
                elif val == 105: stack.append(obj.world)
                else: raise AssertionError(('Unexpected getter', val))
            elif op in (0x05, 0x06, 0x0a, 0x0d):
                right, left = stack.pop(), stack.pop()
                stack.append(left+right if op == 0x05 else left-right if op == 0x06
                    else str(left)+str(right) if op == 0x0a else left <= right)
            elif op in (0x53, 0x54): pc = i['target']
            elif op == 0x55:
                if not stack.pop(): pc = i['target']
            else: raise AssertionError(('Unexpected opcode', op))
        assert stack == ([sentinel] if caller else [])
        assert self.locals[0] == 1

class Tests(unittest.TestCase):
    def test_hook_stack_and_local_bounds(self):
        m = build.emitter()
        self.assertLessEqual(build.stack_peak(m, m.ongoing_hook(), 1), 7)
        self.assertLessEqual(build.stack_peak(m, m.oncoming_hook(), 1), 7)
        self.assertLessEqual(build.stack_peak(m, build.initialize(m)), 18)

    def test_ten_thousand_mixed_events_execute_actual_bytecode(self):
        vm = VM(); rng = random.Random(43)
        hooks = [vm.m.ongoing_hook(), vm.m.oncoming_hook()]
        counts = [0, 0]
        for event in range(10000):
            direction = rng.randrange(2)
            parent = vm.opposite if direction else vm.same
            parent.pos = Vec((rng.randrange(-10000, 10000), rng.randrange(-10000, 10000)))
            sources = [vm.oncoming] if direction else vm.sources
            for node in sources:
                node.pos = Vec((rng.randrange(-100, 100), rng.randrange(-100, 100)))
            targets = [s.world for s in sources]
            vm.run(hooks[direction]); counts[direction] += len(sources)
            pool = vm.props[438][direction]
            self.assertEqual(len(pool), min(16, counts[direction]))
            for clone, target in zip(pool[-len(sources):], targets):
                self.assertEqual(clone.world, target)
                self.assertIs(clone.parent, parent)
            self.assertEqual(vm.group.children, vm.sources)
            self.assertEqual(vm.props[403], [vm.group])
            self.assertEqual(vm.props[386], [vm.oncoming])
            self.assertLessEqual(len(vm.created), 32)
        self.assertEqual(len(vm.created), 32)
        self.assertEqual(len(vm.translated), sum(counts)-32)
        self.assertEqual(len({c.name for c in vm.created}), 32)

    def test_one_direction_cannot_starve_other(self):
        vm = VM()
        for _ in range(100): vm.run(vm.m.ongoing_hook())
        self.assertEqual([len(x) for x in vm.props[438]], [16, 0])
        for _ in range(50): vm.run(vm.m.oncoming_hook())
        self.assertEqual([len(x) for x in vm.props[438]], [16, 16])

    def test_reuse_preserves_identity_appearance_rotation_scale(self):
        vm = VM()
        for _ in range(16): vm.run(vm.m.oncoming_hook())
        pool = vm.props[438][1]; oldest = pool[0]
        before = oldest.appearance, oldest.turns, oldest.scale
        vm.oncoming.appearance = 'different'; vm.oncoming.turns = 2; vm.oncoming.scale = 9
        vm.run(vm.m.oncoming_hook())
        self.assertIs(pool[-1], oldest)
        self.assertEqual((oldest.appearance, oldest.turns, oldest.scale), before)
        self.assertEqual(len(vm.created), 16)

    def test_empty_source_group_does_not_allocate(self):
        vm = VM(); vm.group.children.clear()
        vm.run(vm.m.ongoing_hook())
        self.assertEqual(vm.created, [])

    def test_group_crosses_capacity_mid_loop(self):
        vm = VM()
        vm.sources.append(Node('carC', vm.group, (37, -14)))
        for _ in range(6): vm.run(vm.m.ongoing_hook())
        self.assertEqual(len(vm.created), 16)
        self.assertEqual(len(vm.translated), 2)
        self.assertEqual(vm.group.children, vm.sources)
        self.assertEqual([n.world for n in vm.props[438][0][-3:]],
                         [n.world for n in vm.sources])

    def test_init_replaces_both_lists_without_claiming_scene_cleanup(self):
        vm = VM(); vm.run(vm.m.oncoming_hook()); old = vm.props[438]
        vm.run(build.initialize(vm.m), caller=False)
        self.assertEqual(vm.props[438], [[], []])
        self.assertIsNot(vm.props[438], old)
        self.assertIsNot(vm.props[438][0], vm.props[438][1])
        self.assertEqual(len(vm.created), 1)  # Reset does not delete native models.

    def test_validation_rejects_bad_inputs(self):
        with self.assertRaises(ValueError): build.build(b'bad', b'bad')
        m = build.emitter()
        for code in (bytes.fromhex('41 01 06'), bytes.fromhex('4c 08'),
                     bytes.fromhex('41 01 52 00'), bytes.fromhex('67 41')):
            with self.assertRaises(ValueError): build.stack_peak(m, code)

if __name__ == '__main__':
    unittest.main()
