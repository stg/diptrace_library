"""Shared pad-shape modernization also reaches PCB cache and placement data."""
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.tests.test_dipxml_library import source


PATTERN = '/Board/CacheLib/Slots/Slot/Definition/Pattern'


def document(label, *, report=None):
    root = ElementTree.fromstring(source())
    root.find('Library/Library/PadStyles/PadStyle/MainStack').set('Shape', label)
    return io.parse(ElementTree.tostring(root, encoding='unicode'), report=report or ConversionReport())


class PcbPadShapeConversionTests(unittest.TestCase):
    def test_named_unnamed_and_numeric_shapes_convert_to_every_pcb_format(self):
        for label, code in (('', 5), ('Fiducial', 20), ('10', 10)):
            current = document(label)
            before = dumps(current, preserve=False)
            self.assertEqual(current.one(PATTERN)['PadShape'], code)
            for format in ('dip', 'asc', 'dipxml'):
                with self.subTest(label=label, format=format):
                    output = io.serialize(current, format=format, report=ConversionReport())
                    rebuilt = io.parse(output, report=ConversionReport())
                    self.assertEqual(rebuilt.one(PATTERN)['PadShape'], code)
                    self.assertEqual(rebuilt.one(PATTERN+'/Pads/Pad[1]')['PadShape_New'], code)
                    rebuilt.references.validate()
            self.assertEqual(dumps(current, preserve=False), before)

    def test_unnamed_import_is_reported_without_an_export_only_variant(self):
        report = ConversionReport()
        current = document('', report=report)
        notices = [notice for notice in report.infos if notice.rule == 'empty-pad-shape']
        self.assertTrue(notices)
        self.assertTrue(all(notice.operation == 'import' and notice.format == 'dipxml' for notice in notices))
        with self.assertRaises(TypeError):
            current.one(PATTERN)['PadShape'] = ''
        self.assertEqual(current.one(PATTERN)['PadShape'], 5)
