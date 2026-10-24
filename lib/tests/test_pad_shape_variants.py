"""Empty XML shape labels remain editable and convert only at export."""
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


STYLE = MarkingStyle()
XML_CONTEXT = DchXmlExportContext(units='mm', grid_snap=True, marking_style=STYLE)
ASC_CONTEXT = AscExportContext(units='mm', project_dir='', grid_snap=True, marking_style=STYLE)
PATH = '/Schematic/CacheLib/Slots/Slot/Definition/Pattern'


class PadShapeVariantTests(unittest.TestCase):
    def source(self):
        document = new_schematic()
        slot = document.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
        slot.add('VariablePath', '')
        definition = slot.add('Definition', 0)
        definition.append(new_symbol('Symbol', 'X', placed=False))
        definition.append(new_pattern('Outline'))
        bind_schematic_references(document)
        raw = parse_dchxml(document.to_dchxml_bytes(context=XML_CONTEXT))
        set_attribute(raw.one('/Source/Library/Library/PadStyles/PadStyle/MainStack'), 'Shape', '')
        return raw.as_schematic()

    def test_empty_shape_stays_empty_in_xml_and_uses_reported_numeric_fallback(self):
        source = self.source()
        self.assertEqual(source.one(PATH).scalar('PadShape'), '')
        xml = parse_dchxml(source.to_dchxml_bytes(context=XML_CONTEXT))
        self.assertEqual(xml.one('/Source/Library/Library/PadStyles/PadStyle/MainStack').scalar('Shape'), '')
        for destination in ('dch', 'asc'):
            report = ExportReport()
            if destination == 'dch':
                loaded = parse_dch(source.to_dch_bytes(report=report))
            else:
                loaded = source.as_asc(context=ASC_CONTEXT, report=report).as_schematic()
            self.assertEqual(loaded.one(PATH).scalar('PadShape'), -1)
            notices = [row for row in report.infos if row.rule == 'empty-pad-shape']
            self.assertEqual(len(notices), 1)
            self.assertEqual(notices[0].destination, destination)
            self.assertEqual(source.one(PATH).scalar('PadShape'), '')
            self.assertFalse(source.root.changed)

    def test_editing_shape_replaces_the_empty_variant_without_a_stale_override(self):
        source = self.source()
        source.one(PATH).set_field('PadShape', 2)
        xml = parse_dchxml(source.to_dchxml_bytes(context=XML_CONTEXT))
        self.assertEqual(xml.one('/Source/Library/Library/PadStyles/PadStyle/MainStack').scalar('Shape'), 'Rectangle')
        report = ExportReport()
        self.assertEqual(parse_dch(source.to_dch_bytes(report=report)).one(PATH).scalar('PadShape'), 2)
        self.assertNotIn('empty-pad-shape', [row.rule for row in report.warnings])


if __name__ == '__main__':
    unittest.main()
