"""XML pad-shape aliases modernize into the same editable numeric facts."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import (new_schematic, parse_dchxml, parse_dch, ExportReport,
                        AscExportContext, DchXmlExportContext)
from lib.schematic.formats.dchxml.syntax import (set_attribute)
from lib.schematic.layout.markings import (MarkingStyle)
from lib.schematic.model.objects import (new_symbol, new_pattern)
from lib.schematic.model.refs import (bind_schematic_references)
from lib.schematic.formats.capabilities import DCHXML


STYLE = MarkingStyle()
XML_CONTEXT = DchXmlExportContext(units='mm', grid_snap=True, marking_style=STYLE)
ASC_CONTEXT = AscExportContext(units='mm', project_dir='', grid_snap=True, marking_style=STYLE)
PATH = '/Schematic/CacheLib/Slots/Slot/Definition/Pattern'


class PadShapeVariantTests(unittest.TestCase):
    def source(self, shape=''):
        document = new_schematic()
        slot = document.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
        slot.add('VariablePath', '')
        definition = slot.add('Definition', 0)
        definition.append(new_symbol('Symbol', 'X', placed=False))
        definition.append(new_pattern('Outline'))
        bind_schematic_references(document)
        raw = parse_dchxml(document.to_dchxml_bytes(context=XML_CONTEXT))
        set_attribute(raw.one('/Source/Library/Library/PadStyles/PadStyle/MainStack'), 'Shape', shape)
        return raw.as_schematic()

    def test_empty_main_shape_is_one_numeric_fact_across_all_formats(self):
        source = self.source()
        self.assertEqual(source.one(PATH).scalar('PadShape'), 5)
        xml = parse_dchxml(source.to_dchxml_bytes(context=XML_CONTEXT))
        self.assertEqual(xml.one('/Source/Library/Library/PadStyles/PadStyle/MainStack').scalar('Shape'), '')
        for destination in ('dch', 'asc'):
            report = ExportReport()
            if destination == 'dch':
                loaded = parse_dch(source.to_dch_bytes(report=report))
            else:
                loaded = source.as_asc(context=ASC_CONTEXT, report=report).as_schematic()
            self.assertEqual(loaded.one(PATH).scalar('PadShape'), 5)
            self.assertNotIn('empty-pad-shape', [row.rule for row in report.notices])
            self.assertEqual(source.one(PATH).scalar('PadShape'), 5)
            self.assertFalse(source.root.changed)

    def test_editing_a_normalized_shape_has_no_stale_label(self):
        source = self.source()
        source.one(PATH).set_field('PadShape', 2)
        xml = parse_dchxml(source.to_dchxml_bytes(context=XML_CONTEXT))
        self.assertEqual(xml.one('/Source/Library/Library/PadStyles/PadStyle/MainStack').scalar('Shape'), 'Rectangle')
        report = ExportReport()
        self.assertEqual(parse_dch(source.to_dch_bytes(report=report)).one(PATH).scalar('PadShape'), 2)
        self.assertNotIn('empty-pad-shape', [row.rule for row in report.warnings])

    def test_fiducial_and_unnamed_numeric_aliases_keep_their_actual_codes(self):
        for label, expected, output in (('Fiducial', 20, 'Fiducial'), ('10', 10, '10'), ('5', 5, '')):
            with self.subTest(label=label):
                source = self.source(label)
                self.assertEqual(source.one(PATH)['PadShape'], expected)
                self.assertEqual(parse_dch(source.to_dch_bytes(report=ExportReport())).one(PATH)['PadShape'], expected)
                xml = parse_dchxml(source.to_dchxml_bytes(context=XML_CONTEXT))
                self.assertEqual(xml.one('/Source/Library/Library/PadStyles/PadStyle/MainStack')['Shape'], output)
                self.assertEqual(xml.as_schematic().one(PATH)['PadShape'], expected)

    def test_xml_profiles_keep_inactive_default_shape_geometry(self):
        document = self.source('Ellipse')
        pattern = document.one(PATH)
        pattern['SurfacePad'] = True
        pattern['PadCorner'] = 15
        pattern['PadShape_X'], pattern['PadShape_Y'] = 3, -6
        points = ((0, 0), (3, 0), (3, 6))
        for point in points:
            pattern.one('PadPoints').add('pt', *point)
        for version in DCHXML.write_versions:
            with self.subTest(version=version):
                current = document
                for cycle in range(2):
                    current = parse_dchxml(current.to_dchxml_bytes(version=version,
                        context=XML_CONTEXT, report=ExportReport())).as_schematic()
                    target = current.one(PATH)
                    self.assertEqual((target['PadCorner'], target['PadShape_X'], target['PadShape_Y']),
                                     (15, 3, -6))
                    self.assertEqual(tuple(row.values for row in target.select('PadPoints/pt')), points)


if __name__ == '__main__':
    unittest.main()
