"""Cached checks can outlive the interactive geometry they refer to."""
from decimal import Decimal
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.references import ReferenceError
from lib.pcb.formats import io
from lib.pcb.formats.errors import PcbError
from lib.pcb.formats.dip.decode import decode
from lib.pcb.tests.test_dip_output import configured_document


PATH = '/Board/DesignErrors/DesignError'
TYPES = ('PausedTrace', 'PausedJumperWire', 'PausedVia', 'PausedViaHole')


def source(kinds=TYPES):
    root = ElementTree.fromstring(configured_document().to_dipxml_bytes(report=ConversionReport()))
    errors = root.find('Board/DesignErrors')
    errors.clear()
    for kind in kinds:
        row = ElementTree.SubElement(errors, 'DesignError', dict(X='1', Y='2', Type='Clearance',
            Value='0.1', Rule='0.2', RuleLay='-1', ObjectType1=kind, Object1='-1',
            SubObject1='0', Point1='3', ExtObject1='-1', ObjectType2='-1',
            ObjectNetClass1='-1', ObjectNetClass2='-1'))
        ElementTree.SubElement(row, 'Lays')
    return ElementTree.tostring(root, encoding='utf-8')


class PausedCheckTargetTests(unittest.TestCase):
    def test_saved_editor_targets_import_as_explicit_unavailable_data_with_info(self):
        report = ConversionReport()
        document = io.parse(source(), report=report)
        for index, row in enumerate(document.select(PATH)):
            self.assertEqual(row['ObjectType1'], 24+index)
            self.assertEqual(row.one('UnresolvedTarget1').values, (-1, 0, 3, -1))
            self.assertEqual((row['X'], row['Y'], row['Value'], row['Rule']),
                             (3, -6, Decimal('.3'), Decimal('.6')))
            with self.assertRaises(ReferenceError):
                row['Target1']
        self.assertIn('paused-design-error-targets', {n.rule for n in report.infos})
        self.assertNotIn('unresolved-design-error-targets', {n.rule for n in report.warnings})
        self.assertNotIn('unresolved-reference', {n.rule for n in report.warnings})
        self.assertTrue(all(issue.severity == 'info' for issue in document.references.issues))
        document.references.validate()

    def test_all_outputs_preserve_the_diagnostic_without_synthesizing_a_route(self):
        document = io.parse(source(), report=ConversionReport())
        before = dumps(document, preserve=False)
        traces = len(document.select('/Board/Nets/Net/Traces/Trace'))
        for format in ('dip', 'asc', 'dipxml'):
            report = ConversionReport()
            current = io.parse(io.serialize(document, format=format, report=report), report=report)
            with self.subTest(format=format):
                self.assertEqual(len(current.select('/Board/Nets/Net/Traces/Trace')), traces)
                self.assertEqual([row['ObjectType1'] for row in current.select(PATH)], [24, 25, 26, 27])
                self.assertTrue(all(row.one('UnresolvedTarget1').values == (-1, 0, 3, -1)
                                    for row in current.select(PATH)))
                self.assertNotIn('unresolved-design-error-targets', {n.rule for n in report.warnings})
                self.assertNotIn('unresolved-reference', {n.rule for n in report.warnings})
                current.references.validate()
        self.assertEqual(dumps(document, preserve=False), before)

    def test_numeric_formats_use_their_own_object_codes(self):
        document = io.parse(source(), report=ConversionReport())
        asc = document.as_asc(report=ConversionReport())
        binary = decode(document.to_dip_bytes(report=ConversionReport()))
        for board in (asc.one('/Board'), binary.board):
            self.assertEqual([row.one('ObjectType1').values[0]
                              for row in board.select('DesignErrors/DesignError')], [200, 216, 203, 212])

    def test_editor_indices_do_not_guard_or_bind_unrelated_design_collections(self):
        document = io.parse(source(), report=ConversionReport())
        row = document.one(PATH+'[1]')
        for path in ('Components/Component[1]', 'Nets/Net[1]'):
            node = document.one('/Board/'+path)
            node.move_to(node.parent)
        self.assertEqual(row.one('UnresolvedTarget1').values, (-1, 0, 3, -1))
        row['Target1'] = None  # Explicitly clear the stale selection before repairing it.
        self.assertIsNone(row.child('UnresolvedTarget1'))
        row['ObjectType1'] = 0
        point = document.select('/Board/Nets/Net/Traces/Trace/Points/Point')[0]
        row['Target1'] = point
        self.assertIs(row['Target1'], point)
        self.assertEqual(row['Point1'], point._ordinal())
        document.references.validate()

    def test_unmapped_object_domains_are_still_explicit_errors(self):
        report = ConversionReport()
        with self.assertRaisesRegex(PcbError, 'domain 99'):
            io.parse(source(('99',)), report=report)
        self.assertEqual(len(report.errors), 1)
