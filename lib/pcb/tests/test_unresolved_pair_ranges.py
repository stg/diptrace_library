"""Unavailable imported ranges remain explicit and locally repairable."""
import unittest
from unittest.mock import patch

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import Property, ReferenceError
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.routing import assemble_routing
from lib.pcb.model.objects import new_point, new_trace
from lib.pcb.tests.test_asc_differential_pairs import design as source


MISSING = 'UnresolvedPosEndPointIndex'
ROLE = 'pair-range-pos-end'
CENTER = '/Board/DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint'


def design(*, report=None):
    text = source().replace('(PosLine_EndPoint 1)', '(PosLine_EndPoint 100)')
    operation = lambda text: assemble_routing(prepare_core(text)).document
    return import_diagnostics('asc')(operation)(text, report=report)


class UnresolvedPairRangeTests(unittest.TestCase):
    def test_import_reports_and_retains_the_unresolved_current_selection(self):
        report = ConversionReport()
        document = design(report=report)
        center = document.one(CENTER)
        self.assertEqual((center[MISSING], center['PosTrace_EndPoint']), (100, 100))
        self.assertIsNone(center.child('PosTrace_EndPoint'))
        self.assertIn('unresolved-pair-range', {notice.rule for notice in report.warnings})
        with self.assertRaisesRegex(ReferenceError, 'unresolved'):
            _ = center['PosEndPoint']
        self.assertIsNotNone(center['PosStartPoint'])
        self.assertEqual(len(document.references.issues), 1)
        document.references.validate()

    def test_scope_changes_and_direct_numeric_edits_are_atomic(self):
        document = design(report=ConversionReport())
        center = document.one(CENTER)
        segment = center.parent.parent
        trace = segment['PosTrace']
        original = trace.one('Points/Point[1]')
        other = trace.parent.append(new_trace())
        other.one('Points').append(new_point())
        for action in (lambda: original.move_to(original.parent, 1),
                       lambda: trace.one('Points').append(new_point()),
                       lambda: segment.set('PosTrace', other),
                       lambda: segment.set('PosTrace', None),
                       lambda: document.remove(trace)):
            with self.assertRaises(ReferenceError):
                action()
            self.assertIs(segment['PosTrace'], trace)
            self.assertEqual(center[MISSING], 100)
        with self.assertRaisesRegex(ValueError, 'reference-managed'):
            center[MISSING] = 0
        with self.assertRaises(TypeError):
            center['PosTrace_EndPoint'] = 0
        original['X'] = 42
        self.assertEqual(original['X'], 42)
        document.references.validate()

    def test_repair_and_disconnect_update_consumers_without_global_scans(self):
        for disconnect in (False, True):
            with self.subTest(disconnect=disconnect):
                document = design(report=ConversionReport())
                center = document.one(CENTER)
                segment = center.parent.parent
                trace = segment['PosTrace']
                target = None if disconnect else trace.one('Points/Point[2]')
                probe = document.root.add('Probe', 100)
                document.references.bind(probe, center, Property(probe, 'PosTrace_EndPoint'))
                with self.assertRaises(ReferenceError):
                    center['PosEndPoint'] = design(report=ConversionReport()).one(CENTER)['PosStartPoint']
                self.assertEqual((center[MISSING], probe.values), (100, (100,)))
                with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                     patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
                    center['PosEndPoint'] = target
                    self.assertIs(center['PosEndPoint'], target)
                    self.assertIsNone(center.child(MISSING))
                    self.assertEqual(probe.values, (-1 if disconnect else 1,))
                self.assertEqual(document.references.issues, [])
                trace.one('Points/Point[1]').move_to(trace.one('Points'), 1)
                document.references.validate()

    def test_clone_and_owned_removal_keep_guards_scoped(self):
        document = design(report=ConversionReport())
        clone = document.clone()
        center = clone.one(CENTER)
        self.assertEqual(center[MISSING], 100)
        self.assertIs(clone.references.issues[0].collections[0], center.parent.parent['PosTrace'].one('Points'))
        center['PosEndPoint'] = None
        self.assertEqual(document.one(CENTER)[MISSING], 100)
        # Removing the entire owner discards its own unresolved relationships.
        owner = document.one('/Board/DifferentialPairs/DifferentialPair')
        document.one('/Board/Nets/Net[1]/Traces/Trace')['Target1'] = None
        document.remove(owner)
        self.assertEqual(document.references.issues, [])
        document.references.validate()

    def test_copy_preserves_scope_and_incompatible_destination_is_rejected(self):
        document = design(report=ConversionReport())
        center = document.one(CENTER)
        copied = document.copy(center)
        self.assertEqual(copied[MISSING], 100)
        self.assertEqual(len(document.references.issues), 2)
        document.remove(copied)
        other_segment = document.copy(center.parent.parent)
        other_center = other_segment.one('CenterPoints/CenterPoint')
        self.assertEqual(other_center[MISSING], 100)
        other_center['PosStartPoint'], other_center['PosEndPoint'] = None, None
        other_trace = other_segment['PosTrace'].parent.append(new_trace())
        other_trace.one('Points').append(new_point())
        other_segment['PosTrace'] = other_trace
        original_parent = center.parent
        with self.assertRaises(ReferenceError):
            center.move_to(other_segment.one('CenterPoints'))
        self.assertIs(center.parent, original_parent)
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
