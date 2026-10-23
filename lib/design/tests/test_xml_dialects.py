"""Both verified XML vocabularies populate the same editable geometry."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lib.design import new_schematic, parse_dchxml, DchXmlExportContext
from lib.design.dchxml import set_attribute
from lib.design.markings import MarkingStyle
from lib.design.schematic_objects import new_symbol, new_symbol_shape, new_pattern, new_pattern_shape
from lib.design.schematic_refs import bind_schematic_references


CONTEXT = DchXmlExportContext(units='mm', grid_snap=True, marking_style=MarkingStyle())


class XmlDialectTests(unittest.TestCase):
    def source(self):
        document = new_schematic()
        slot = document.one('/Schematic/CacheLib/Slots').add('Slot', 0, '')
        slot.add('VariablePath', '')
        definition = slot.add('Definition', 0)
        symbol = definition.append(new_symbol('Label', 'X', placed=False))
        text = symbol.one('Shapes').append(new_symbol_shape())
        text.set_field('Type', 10)
        text.one('TextLine').add('pt', 'symbol text')
        text.one('Points_New').add('pt', 3, 6)
        pattern = definition.append(new_pattern('Outline'))
        pattern.set_field('PadShape', 3)
        for xy in ((0, 0), (3, 6), (-3, 6)):
            pattern.one('PadPoints').add('pt', *xy)
        drawing = pattern.one('Shapes').insert(new_pattern_shape(1, kind=7), 1)
        drawing.one('TextLine').add('pt', 'footprint text')
        drawing.one('Points_New').add('pt', 6, 9)
        bind_schematic_references(document)
        return document

    def test_versioned_point_and_text_names_keep_editable_geometry(self):
        source = self.source()
        for version in (46, 47, 48):
            raw = parse_dchxml(source.to_dchxml_bytes(context=CONTEXT, version=version))
            row, lines, line = ('Item', 'Lines', 'Item') if version == 46 else ('Point', 'TextLines', 'TextLine')
            library = raw.one('/Source/Library')
            self.assertEqual(len(library.select('Library/PadStyles/PadStyle/MainStack/Points/'+row)), 3)
            self.assertEqual(library.one('Components/Component/Part/Shapes/Shape/'+lines+'/'+line).values, ('symbol text',))
            self.assertEqual(library.one('Library/Patterns/Pattern/Shapes/Shape/'+lines+'/'+line).values, ('footprint text',))
            imported = raw.as_schematic()
            definition = imported.one('/Schematic/CacheLib/Slots/Slot/Definition')
            self.assertEqual(definition.one('Part/Shapes/Shape/Points_New/pt').values, (3, 6))
            drawing = definition.one('Pattern/Shapes/Shape[2]')
            self.assertEqual(drawing.one('Points_New/pt').values, (6, 9))
            self.assertEqual(drawing.one('TextLine/pt').values, ('footprint text',))
            drawing.one('Points_New/pt').set_values(12, 15)
            changed = parse_dchxml(imported.to_dchxml_bytes(context=CONTEXT, version=version))
            point = changed.one('/Source/Library/Library/Patterns/Pattern/Shapes/Shape/Points/'+row)
            self.assertEqual((point.scalar('X'), point.scalar('Y')), (4, -5))
            self.assertFalse(raw.root.changed)
        self.assertEqual(source.one('/Schematic/CacheLib/Slots/Slot/Definition/Part/Shapes/Shape/Points_New/pt').values, (3, 6))
        self.assertEqual(source.one('/Schematic/CacheLib/Slots/Slot/Definition/Pattern/Shapes/Shape[2]/Points_New/pt').values, (6, 9))

    def test_unknown_rows_and_duplicate_alternative_containers_still_fail(self):
        raw = parse_dchxml(self.source().to_dchxml_bytes(context=CONTEXT, version=48))
        shape = raw.one('/Source/Library/Components/Component/Part/Shapes/Shape')
        unknown = shape.one('Points').add('UnknownVertex')
        set_attribute(unknown, 'X', 1)
        set_attribute(unknown, 'Y', 2)
        with self.assertRaisesRegex(ValueError, 'unsupported XML fields'):
            raw.as_schematic()
        unknown.detach()
        shape.add('Lines')
        with self.assertRaisesRegex(ValueError, 'expected at most one of'):
            raw.as_schematic()


if __name__ == '__main__':
    unittest.main()
