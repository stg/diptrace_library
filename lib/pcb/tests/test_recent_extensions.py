"""Later gates keep identities, shield relationships and font values aligned."""
from decimal import Decimal
import unittest

from lib.common.binary import BinaryWriter
from lib.common.library_codec import CachedDefinitionInput
from lib.common.model import Element
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.recent import read_recent_extensions


def pair(parent, collection, kind, *, separate):
    node = parent.add(collection).add(kind)
    segment = node.add('Segments').add('Segment')
    center = segment.add('CenterPoints').add('CenterPoint')
    center.add('PosPoints').add('PosPoint')
    center.add('NegPoints').add('NegPoint')
    if separate:
        for side in ('Pos', 'Neg'):
            node.add(side+'SeparateTraces').add(side+'Trace').add('Points').add('Point')
    return node


def board_fragment():
    board = Element('Board')
    board.add('Panel')
    board.add('CompFontSize', 2)
    component = board.add('Components').add('Component')
    component.add('MarkingFontSize', 2)
    pattern = component.add('Pattern')
    pattern.add('Pads').add('Pad')
    pattern.add('Shapes').add('Shape').add('FontSize', 2)
    pattern.add('Dimensions').add('Dimension').add('FontSize', 2)
    points = board.add('Nets').add('Net').add('Traces').add('Trace').add('Points')
    points.add('Point')
    points.add('Point')
    pair(board, 'DifferentialPairs', 'DifferentialPair', separate=True)
    pair(board, 'RemovedDifferentialPairs', 'RemovedDifferentialPair', separate=False)
    board.add('CopperPours').add('CopperPour')
    board.add('Shapes').add('Shape').add('FontSize', 2)
    board.add('Dimensions').add('Dimension').add('FontSize', 2)
    table = board.add('Tables').add('Table')
    table.add('FontSize', 2)
    table.add('Cells').add('Cell').add('FontSize', 2)
    sheet = board.add('SheetSettings')
    sheet.add('BorderZones').add('FontSize', 2)
    titles = sheet.add('TitleBlocks')
    for _ in range(2):
        titles.add('TitleBlock').add('Contents').add('Content').add('FontSize', 2)
    definition = Element('Definition')
    part = definition.add('Part')
    part.add('Pins').add('Pin').add('NameFontSize', 2)
    part.add('Shapes').add('Shape').add('FontSize', 2)
    pattern = definition.add('Pattern')
    pattern.add('Shapes').add('Shape').add('FontSize', 2)
    pattern.add('Dimensions').add('Dimension').add('FontSize', 2)
    return board, definition


def font_expectations(board, definition):
    return [(board.one('Components/Component'), 'MarkingFontSize', None, '2.125'),
            (board.one('Components/Component/Pattern/Shapes/Shape'), 'FontSize', 'FontMono', '3.25'),
            (board.one('Components/Component/Pattern/Dimensions/Dimension'), 'FontSize', 'FontMono', '4.375'),
            (board.one('Shapes/Shape'), 'FontSize', 'FontMono', '5.5'),
            (board.one('Dimensions/Dimension'), 'FontSize', 'FontMono', '6.625'),
            (board.one('Tables/Table'), 'FontSize', 'DefFontMono', '7.75'),
            (board.one('Tables/Table/Cells/Cell'), 'FontSize', 'FontMono', '8.875'),
            (board, 'CompFontSize', 'CompFontMono', '9.125'),
            (board.one('SheetSettings/BorderZones'), 'FontSize', None, '10.25'),
            (board.one('SheetSettings/TitleBlocks/TitleBlock[1]/Contents/Content'), 'FontSize', 'FontMono', '11.375'),
            (board.one('SheetSettings/TitleBlocks/TitleBlock[2]/Contents/Content'), 'FontSize', 'FontMono', '12.5'),
            (definition.one('Part/Pins/Pin'), 'NameFontSize', 'NameFontMono', '13.625'),
            (definition.one('Part/Shapes/Shape'), 'FontSize', 'FontMono', '14.75'),
            (definition.one('Pattern/Shapes/Shape'), 'FontSize', 'FontMono', '15.875'),
            (definition.one('Pattern/Dimensions/Dimension'), 'FontSize', 'FontMono', '16.125')]


class RecentExtensionTests(unittest.TestCase):
    def test_shield_values_belong_to_each_center_and_follow_its_side_points(self):
        board, definition = board_fragment()
        centers = board.one('DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints')
        center = centers.add('CenterPoint')
        positive = center.add('PosPoints')
        positive.add('PosPoint')
        positive.add('PosPoint')
        center.add('NegPoints').add('NegPoint')
        writer = BinaryWriter()
        writer.buffer.extend(b'\x07DTBOARD')
        writer.integer(57)
        for gap in (1, 2, 3, 4):
            writer.number(gap)
        writer.integer(101)
        for group in range(10, 31):
            writer.integer(group)
        writer.integer(90)
        writer.integer(31)
        writer.integer(42)
        reader = Reader(bytes(writer.buffer))
        read_recent_extensions(reader, board, (CachedDefinitionInput(definition, ()),))
        first, second = centers.children()
        self.assertEqual((first['PosShieldGroup'], first['NegShieldGroup']), (15, 16))
        self.assertEqual((second['PosShieldGroup'], second['NegShieldGroup']), (19, 20))
        self.assertEqual([point['ShieldGroup'] for point in second.select('PosPoints/PosPoint')], [21, 22])
        self.assertEqual(second.one('NegPoints/NegPoint')['ShieldGroup'], 23)
        self.assertEqual(board.one('DifferentialPairs/DifferentialPair/PosSeparateTraces/PosTrace/Points/Point')['ShieldGroup'], 24)
        self.assertIsNone(centers.parent.child('PosShieldGroup'))
        self.assertEqual(board.one('CopperPours/CopperPour')['ShieldGroup'], 30)
        self.assertEqual(reader.integer(), 42)
        self.assertEqual(reader.pos, len(reader.data))

    def test_every_recent_revision_stops_at_its_own_boundary(self):
        for version in range(54, 63):
            with self.subTest(version=version):
                board, definition = board_fragment()
                fonts = font_expectations(board, definition)
                writer = BinaryWriter()
                writer.buffer.extend(b'\x07DTBOARD')
                writer.integer(version)
                if version > 54:
                    for value in (1, 2, 3, 4):
                        writer.number(value)
                if version > 55:
                    writer.integer(101)
                if version > 56:
                    for group in range(10, 26):
                        writer.integer(group)
                    writer.integer(90)
                    writer.integer(26)
                if version > 57:
                    writer.integer(27)
                if version > 58:
                    writer.boolean(True)
                if version > 59:
                    writer.boolean(version % 2 == 0)
                if version > 60:
                    for index, (_, _, mono, size) in enumerate(fonts):
                        if mono:
                            writer.boolean(bool(index % 2))
                        writer.number(Decimal(size))
                if version > 61:
                    writer.boolean(True)
                writer.integer(17)
                reader = Reader(bytes(writer.buffer))
                read_recent_extensions(reader, board, (CachedDefinitionInput(definition, ()),))
                self.assertEqual(reader.integer(), 17)
                self.assertEqual(reader.pos, len(reader.data))
                if version > 55:
                    self.assertEqual(board.one('Nets/Net')['HiddenId'], 101)
                if version > 56:
                    self.assertEqual(board['ShieldGroup'], 90)
                    self.assertEqual(board.one('Components/Component/Pattern/Pads/Pad')['ShieldGroup'], 11)
                    self.assertEqual(board.one('DifferentialPairs/DifferentialPair/Segments/Segment/CenterPoints/CenterPoint')['PosShieldGroup'], 15)
                    self.assertEqual(board.one('RemovedDifferentialPairs/RemovedDifferentialPair/Segments/Segment/CenterPoints/CenterPoint')['NegShieldGroup'], 22)
                    self.assertEqual(board.one('CopperPours/CopperPour')['ShieldGroup'], 25)
                    self.assertEqual(definition.one('Pattern/Shapes/Shape')['ShieldGroup'], 26)
                if version > 58:
                    self.assertTrue(board.one('Shapes/Shape')['PictureFlipped'])
                self.assertEqual(board['SchemNetClasses'], version > 59 and version % 2 == 0)
                if version > 60:
                    for index, (owner, size, mono, expected) in enumerate(fonts):
                        self.assertEqual(owner[size], Decimal(expected))
                        self.assertEqual(len(owner.children(size)), 1)
                        if mono:
                            self.assertEqual(owner[mono], bool(index % 2))
                if version > 61:
                    self.assertTrue(board.one('Nets/Net')['AllowLoops'])


if __name__ == '__main__':
    unittest.main()
