"""Cached drawings remain authored content when XML omits instance-only flags."""
import unittest

from lib import ConversionReport, parse, serialize
from lib.common.asc import dumps as model_text
from lib.schematic.formats.capabilities import DCHXML
from lib.schematic.model.objects import new_symbol_shape
from lib.tests.test_legacy_groups import source


class XmlCachedDrawingFlagTests(unittest.TestCase):
    def test_cached_text_is_retained_and_flags_are_reported_on_the_detached_output(self):
        document = source()
        part = document.one('/Schematic/CacheLib/Slots/Slot/Definition/Part')
        drawing = part.one('Shapes').append(new_symbol_shape())
        drawing['Type'], drawing['PenWidth'] = 10, 0
        drawing['ShowPart'], drawing['MarkingGenerated'] = True, True
        drawing.one('TextLine').add('pt', 'unplaced text')
        drawing.one('Points_New').add('pt', 3, -6)
        before = model_text(document, preserve=False)
        for version in DCHXML.write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                rebuilt = parse(serialize(document, format='dchxml', version=version, report=report),
                                report=ConversionReport())
                shape = rebuilt.one(part.path+'/Shapes/Shape')
                self.assertEqual(shape.one('TextLine/pt').values, ('unplaced text',))
                self.assertEqual(shape.one('Points_New/pt').values, (3, -6))
                self.assertFalse(shape['ShowPart'])
                self.assertFalse(shape['MarkingGenerated'])
                self.assertEqual(len([n for n in report.warnings if n.rule == 'cached-drawing-flags']), 1)
                self.assertEqual(report.errors, [])
                self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
