"""A marking option must not change an ordinary placed drawing's kind."""
import unittest

import lib
from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.schematic.formats.capabilities import DCH
from lib.schematic.formats.dch.read import Reader
from lib.schematic.formats.dch.write import Writer
from lib.schematic.model.objects import new_symbol, new_symbol_shape


def drawing_document(kind, generated):
    document = lib.new_schematic()
    part = document.one('/Schematic/Components').append(new_symbol('Drawing', 'U1'))
    part['Width'], part['Height'] = 18, 12
    drawing = part.one('Shapes').append(new_symbol_shape())
    drawing['Type'], drawing['MarkingGenerated'] = kind, generated
    for point in ((0, 0), (9.125, 1.5)):
        drawing.one('Points_New').add('pt', *point)
    return document, part, drawing


class DchDrawingTagTests(unittest.TestCase):
    def test_placed_tag_requires_both_text_kind_and_generated_option(self):
        for version in DCH.write_versions:
            for kind in (1, 2, 10):
                for generated in (False, True):
                    with self.subTest(version=version, kind=kind, generated=generated):
                        document, part, drawing = drawing_document(kind, generated)
                        before = dumps(document, preserve=False)
                        writer = Writer(version)
                        writer.buffer.extend(b'\x07DTSCHEM')
                        writer.integer(version)
                        writer.symbol_shapes(part)
                        reader = Reader(bytes(writer.buffer))
                        self.assertEqual(reader.count('shapes'), 1)
                        self.assertTrue(reader.boolean())
                        reader.integer()  # Coarse text orientation precedes the kind.
                        expected = 700 if kind == 10 and generated else kind
                        self.assertEqual(reader.integer(), expected)
                        self.assertEqual(drawing['Type'], kind)
                        self.assertEqual(dumps(document, preserve=False), before)

    def test_complete_output_preserves_flagged_line_geometry_and_stabilizes(self):
        document, _, drawing = drawing_document(1, True)
        document.validate()
        before = dumps(document, preserve=False)
        wanted_points = tuple(point.values for point in drawing.select('Points_New/pt'))
        for version in DCH.write_versions:
            with self.subTest(version=version):
                data = lib.serialize(document, format='dch', version=version, report=ConversionReport())
                loaded = lib.parse(data, report=ConversionReport())
                # Output may also materialize the component's calculated labels.
                restored, = [shape for shape in loaded.select('/Schematic/Components/Part/Shapes/Shape')
                    if tuple(point.values for point in shape.select('Points_New/pt')) == wanted_points]
                self.assertEqual(restored['Type'], 1)
                self.assertTrue(restored['MarkingGenerated'])
                self.assertEqual(lib.serialize(loaded, format='dch', version=version,
                                               report=ConversionReport()), data)
                self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
