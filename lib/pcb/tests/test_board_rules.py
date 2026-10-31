"""Copper-stack and rule identities remain coherent through ordinary edits."""
import unittest
from unittest.mock import patch

from lib.common.references import Property, ReferenceError
from lib.pcb.model.objects import (new_document, new_layer, new_via_style, new_net_class,
                                   new_net, new_trace, new_point)


class BoardRuleTests(unittest.TestCase):
    def design(self):
        document = new_document()
        board = document.one('/Board')
        layers = board.one('Layers')
        top, bottom = layers.children()
        inner = layers.append(new_layer('Inner'))
        inner.move_to(layers, 1)
        style = board.one('ViaStyles').append(new_via_style('Via', size=2, hole_size=1))
        net = board.one('Nets').append(new_net('Signal'))
        trace = net.one('Traces').append(new_trace())
        point = trace.one('Points').append(new_point())
        return document, top, inner, bottom, style, net, point

    def probe(self, document, source, *fields):
        probe = document.root.add('Probe', *(False if isinstance(source[name], bool) else 0 for name in fields))
        document.references.bind(probe, source,
            *(Property(probe, field, argument=index) for index, field in enumerate(fields)), role='probe')
        return probe

    def test_through_span_has_no_saved_layer_indices_and_tracks_stack_changes(self):
        document, top, inner, bottom, style, _, _ = self.design()
        probe = self.probe(document, style, 'Lay1', 'Lay2', 'Through')
        self.assertIsNone(style['Span'])
        self.assertTrue(style['Through'])
        self.assertIs(style['FromLayer'], top)
        self.assertIs(style['ToLayer'], bottom)
        self.assertIsNone(style.child('Through'))
        extra = bottom.parent.append(new_layer('New bottom'))
        self.assertIs(style['ToLayer'], extra)
        self.assertEqual(probe.values, (0, 3, True))
        document.validate()

    def test_bounded_span_is_one_atomic_identity_fact(self):
        document, top, inner, bottom, style, _, _ = self.design()
        style['Span'] = (top, inner)
        probe = self.probe(document, style, 'Lay1', 'Lay2', 'Through')
        self.assertEqual(probe.values, (0, 1, False))
        style['Span'] = (inner, bottom)
        self.assertEqual(style['Span'], (inner, bottom))
        self.assertEqual(probe.values, (1, 2, False))
        style['Span'] = None
        self.assertEqual(probe.values, (0, 2, True))
        self.assertEqual(len(document.references.outgoing(style)), 0)
        document.validate()

    def test_span_failure_and_layer_reversal_do_not_partly_mutate(self):
        document, top, inner, bottom, style, _, _ = self.design()
        style['Span'] = (top, inner)
        before = tuple(document.references)
        for bounds in ((inner, top), (top, top), (top,), (top, None)):
            with self.assertRaises((ReferenceError, ValueError, TypeError)):
                style['Span'] = bounds
            self.assertEqual(style['Span'], (top, inner))
            self.assertEqual(tuple(document.references), before)
        # No value-copy consumer is necessary for the ordering constraint.
        with self.assertRaisesRegex(ReferenceError, 'stack order'):
            inner.move_to(inner.parent, 0)
        self.assertEqual(inner._ordinal(), 1)
        link = document.references.outgoing(style, role='via-span-from')[0]
        with self.assertRaises(ReferenceError):
            document.references.discard(link)
        self.assertEqual(style['Span'], (top, inner))
        document.validate()

    def test_explicit_outer_layer_span_stays_bounded_when_the_stack_grows(self):
        document, top, _, bottom, style, _, _ = self.design()
        style['Span'] = (top, bottom)
        bottom.parent.append(new_layer('New bottom'))
        self.assertFalse(style['Through'])
        self.assertIs(style['ToLayer'], bottom)
        self.assertEqual(style['Lay2'], 2)
        document.validate()

    def test_layer_via_and_class_indices_follow_identities_without_global_scans(self):
        document, top, inner, bottom, style, net, point = self.design()
        board = document.one('/Board')
        first = board.one('NetClasses').append(new_net_class('First'))
        second = first.parent.append(new_net_class('Second'))
        other_style = style.parent.append(new_via_style('Another'))
        point['Layer'], point['Via'], net['Class'] = inner, style, second
        layer_copy = self.probe(document, point, 'Lay', 'ViaStyle')
        class_copy = self.probe(document, net, 'NetClass')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            inner.move_to(inner.parent, 0)
            other_style.move_to(other_style.parent, 0)
            second.move_to(second.parent, 0)
            self.assertEqual(layer_copy.values, (0, 1))
            self.assertEqual(class_copy.values, (0,))
            point['Layer'] = bottom
            self.assertEqual(layer_copy.values, (2, 1))
        self.assertIs(point['Via'], style)
        self.assertIs(net['Class'], second)
        document.validate()

    def test_different_board_targets_and_referenced_deletion_are_rejected(self):
        document, top, inner, _, style, _, point = self.design()
        point['Layer'] = inner
        foreign = new_document().one('/Board/Layers/Layer[1]')
        with self.assertRaises(ReferenceError):
            point['Layer'] = foreign
        with self.assertRaises(ReferenceError):
            style['Span'] = (top, foreign)
        with self.assertRaises(ReferenceError):
            document.remove(inner)
        self.assertIs(point['Layer'], inner)
        point['Layer'] = None
        document.remove(inner)
        document.validate()

    def test_clone_remaps_spans_and_reference_users(self):
        document, top, inner, _, style, net, point = self.design()
        style['Span'] = (top, inner)
        point['Layer'], point['Via'] = inner, style
        duplicate = document.clone()
        copied_style = duplicate.one('/Board/ViaStyles/ViaStyle')
        self.assertEqual(copied_style['Span'], tuple(duplicate.select('/Board/Layers/Layer')[:2]))
        copied_point = duplicate.one('/Board/Nets/Net/Traces/Trace/Points/Point')
        self.assertIs(copied_point['Via'], copied_style)
        self.assertIs(copied_point['Layer'], copied_style['ToLayer'])
        self.assertIsNot(copied_point['Layer'], inner)
        duplicate.validate()
        document.validate()

    def test_plane_assignment_prevents_disabling_its_net(self):
        document = new_document()
        board = document.one('/Board')
        net = board.one('Nets').append(new_net('Plane'))
        layer = board.one('Layers/Layer[1]')
        layer['Net'] = net
        with self.assertRaises(ReferenceError):
            net['Enabled'] = False
        self.assertTrue(net['Enabled'])
        self.assertIs(layer['Net'], net)
        document.validate()


if __name__ == '__main__':
    unittest.main()
