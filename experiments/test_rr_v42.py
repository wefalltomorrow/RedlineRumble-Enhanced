#!/usr/bin/env python3
"""Source-only checks: strict three-local VM, cap, CFG liveness and stack.

This executes the corrected clone hooks in a small test model, not Director.
No proprietary game data is needed by CI.
"""
import unittest
import build_rr_v42 as v42
import build_rr_v39 as v39

v35 = v42.legacy


def hooks():
    original = v35.create_one_visual
    try:
        v35.create_one_visual = lambda b, oc: v39.bounded_clone(v35, original, b, oc)
        return v35.ongoing_hook(), v35.oncoming_hook()
    finally:
        v35.create_one_visual = original


def corrected_hooks():
    # Real handlers have a return after these hook fragments. Keep the
    # production decoder's strict branch checks when testing fragments.
    return tuple(v42.correct_locals(code + b'\x01')[0][:-1] for code in hooks())


class Model:
    def __init__(self, name, parent=None):
        self.name, self.children, self.parent = name, [], None
        if parent:
            parent.add_child(self)

    def add_child(self, child):
        if child.parent:
            child.parent.children.remove(child)
        self.children.append(child)
        child.parent = self


class Machine:
    def __init__(self):
        self.forward, self.opposite = Model('forward'), Model('opposite')
        self.group = Model('group', self.forward)
        self.sources = [Model('same'+str(i), self.group) for i in range(3)]
        self.oncoming = Model('oncoming', self.opposite)
        self.props = {438: [], 403: [self.group], 386: [self.oncoming],
                      401: self.forward, 402: self.opposite}
        self.locals = [1, None, None]  # Exactly the declared three slots.
        self.allocations, self.names = 0, set()

    def run(self, code):
        instructions = {i['s']: i for i in v35.decode(code, allow_end=True)}
        stack, pc, steps = [], 0, 0
        while pc < len(code):
            steps += 1
            assert steps < 5000
            i = instructions[pc]
            op, arg, pc = i['op'], i['val'], i['e']
            if op == 0x41:
                stack.append(arg)
            elif op == 0x44:
                stack.append({11: 'rear', 14: '_'}[arg])
            elif op == 0x45:
                stack.append(('symbol', arg))
            elif op == 0x4a:
                stack.append(self.props[arg])
            elif op in (0x4c, 0x52):
                if not 0 <= arg < len(self.locals):
                    raise IndexError('Undeclared local index ' + str(arg))
                if op == 0x4c:
                    stack.append(self.locals[arg])
                else:
                    self.locals[arg] = stack.pop()
            elif op == 0x61:
                assert arg == 66
                stack.append(len(stack.pop()))
            elif op in (0x05, 0x0a, 0x0d):
                right, left = stack.pop(), stack.pop()
                stack.append(left+right if op == 0x05 else str(left)+str(right) if op == 0x0a else left <= right)
            elif op in (0x42, 0x43):
                stack.append((arg, op == 0x43))
            elif op == 0x67:
                count, returns = stack.pop()
                args = stack[-count:]
                del stack[-count:]
                receiver, result = args[0], None
                if arg == 65:
                    result = receiver[args[1]-1]
                elif arg == 36:
                    assert args[1] == ('symbol', 434)
                    result = receiver.children[args[2]-1]
                elif arg == 66:
                    assert args[1] == ('symbol', 434)
                    result = len(receiver.children)
                elif arg == 153:
                    assert args[1] not in self.names
                    result = Model(args[1], receiver.parent)
                    self.names.add(args[1])
                    self.allocations += 1
                elif arg == 316:
                    assert args[2] == ('symbol', 436)
                    receiver.add_child(args[1])
                elif arg == 78:
                    receiver.append(args[1])
                else:
                    raise AssertionError(('Unexpected method', arg))
                if returns:
                    stack.append(result)
            elif op in (0x53, 0x54):
                pc = i['target']
            elif op == 0x55:
                if not stack.pop():
                    pc = i['target']
            else:
                raise AssertionError(('Unexpected opcode', op))
        assert stack == []


class LocalIndexChecks(unittest.TestCase):
    def test_legacy_hooks_fail_strict_local_bounds(self):
        for code in hooks():
            with self.assertRaises(IndexError):
                Machine().run(code)

    def test_corrected_hooks_both_directions_and_cap(self):
        same, opposite = corrected_hooks()
        vm = Machine()
        source_children = list(vm.group.children)
        for _ in range(8):
            vm.run(same)
            vm.run(opposite)
        self.assertEqual(vm.allocations, 32)
        self.assertEqual(len(vm.props[438]), 32)
        identities = list(vm.props[438])
        for _ in range(40):
            vm.run(same)
            vm.run(opposite)
        self.assertEqual(vm.props[438], identities)
        self.assertEqual(vm.allocations, 32)
        self.assertEqual(vm.group.children, source_children)
        self.assertEqual(vm.props[403], [vm.group])
        self.assertEqual(vm.props[386], [vm.oncoming])
        self.assertEqual(vm.locals[0], 1)
        self.assertEqual(vm.locals[2], 4)

    def test_group_loop_crosses_cap_without_adding_extra_models(self):
        same, opposite = corrected_hooks()
        vm = Machine()
        for _ in range(31):
            vm.run(opposite)
        vm.run(same)
        self.assertEqual(vm.allocations, 32)
        self.assertEqual(len(vm.group.children), 3)
        self.assertEqual(vm.locals[2], 4)

    def test_exact_eleven_operand_changes_and_unchanged_branches(self):
        changes = []
        for code in hooks():
            # Standalone hooks branch to their end; append return for decoder.
            fixed, edits = v42.correct_locals(code+b'\x01')
            changes.extend(edits)
            before, after = v35.decode(code+b'\x01'), v35.decode(fixed)
            self.assertEqual(len(before), len(after))
            for a, b in zip(before, after):
                self.assertEqual((a['s'], a['e'], a['op'], a['target']),
                                 (b['s'], b['e'], b['op'], b['target']))
                if a['op'] not in (0x4c, 0x52):
                    self.assertEqual(a['raw'], b['raw'])
        self.assertEqual(len(changes), 11)
        self.assertEqual(sum(e['from'] == 8 for e in changes), 6)
        self.assertEqual(sum(e['from'] == 16 for e in changes), 5)

    def test_stack_paths_within_original_seven_slots(self):
        for code in hooks():
            self.assertEqual(v42.hook_stack_bound(code), 4)
        with self.assertRaises(ValueError):
            v42.hook_stack_bound(v35.op(0x52, 1))
        with self.assertRaises(ValueError):
            v42.hook_stack_bound(v35.op(0x41, 1))

    def test_reject_unknown_indices_and_wrong_baseline(self):
        for index in (3, 7, 17):
            with self.assertRaises(ValueError):
                v42.correct_locals(v35.op(0x4c, index))
        with self.assertRaises(ValueError):
            v42.build(b'wrong movie')

    def test_cfg_liveness_catches_conditional_path(self):
        b = v35.Seq()
        b.emit(0x41, 0)
        b.jmp(0x55, 'read')
        b.emit(0x41, 1)
        b.emit(0x52, 1)
        b.emit(0x01)
        b.label('read')
        b.emit(0x4c, 1)
        b.emit(0x01)
        with self.assertRaises(ValueError):
            v42.dead_until_written(b.resolved(), 0, 1)
        safe = v35.op(0x41, 1)+v35.op(0x52, 1)+v35.op(0x4c, 1)+b'\x01'
        self.assertEqual(v42.dead_until_written(safe, 0, 1), 2)

    def test_cfg_liveness_handles_backward_edges(self):
        b = v35.Seq()
        b.label('read')
        b.emit(0x4c, 1)
        b.label('entry')
        b.jmp(0x54, 'read')
        with self.assertRaises(ValueError):
            v42.dead_until_written(b.resolved(), b.labels['entry'], 1)


if __name__ == '__main__':
    unittest.main()
