"""Revision sections retain authored settings and replace obsolete precision."""
from decimal import Decimal
import unittest

from lib.common.binary import BinaryWriter
from lib.common.library_codec import CachedDefinitionInput
from lib.common.model import Element
from lib.pcb.formats.dip.layer_stack import read_layer_stack
from lib.pcb.formats.dip.length_rules import read_length_rules
from lib.pcb.formats.dip.masks import read_mask_extensions
from lib.pcb.formats.dip.meanders import read_meanders
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.settings import read_camera_extension, read_grid_extension


def stream(version):
    writer = BinaryWriter()
    writer.buffer.extend(b'\x07DTBOARD')
    writer.integer(version)
    return writer


def write_values(writer, kind, *items):
    for item in items:
        getattr(writer, kind)(item)


def board_fragment():
    board = Element('Board')
    board.add('Settings').add('GridSize', 1)
    pads = board.add('Components').add('Component').add('Pattern').add('Pads')
    pads.add('Pad')
    pads.add('Pad')
    board.add('NetClasses').add('NetClass')
    board.add('Nets').add('Net')
    board.add('Tables').add('Table')
    return board


def write_rule(writer, name, *, connection):
    writer.text(name)
    write_values(writer, 'number', 30, .3)
    write_values(writer, 'boolean', True, False)
    write_values(writer, 'integer', 0, 1, int(connection))
    if connection:
        write_values(writer, 'integer', 2, 0, 1, 3, 4)
        writer.number(29)
        writer.boolean(True)


class RevisionSectionTests(unittest.TestCase):
    def test_layer_materials_and_length_rules_keep_named_ownership(self):
        for version in (43, 54, 62):
            with self.subTest(version=version):
                writer = stream(version)
                writer.text('Two layer')
                writer.integer(2)
                for layer, name, kind, variable in ((0, 'Copper', 0, False), (-1, 'Core', 2, True)):
                    writer.integer(layer)
                    writer.text(name)
                    writer.integer(kind)
                    writer.boolean(variable)
                    write_values(writer, 'number', .3, 4.2, .9)
                write_values(writer, 'number', .1, .2)
                write_values(writer, 'boolean', True, False)
                write_rule(writer, 'Main', connection=True)
                writer.integer(1)
                write_rule(writer, 'Clock group', connection=False)
                write_values(writer, 'number', .6, 60)
                writer.boolean(True)
                write_values(writer, 'integer', 2, 1, 17)
                reader = Reader(bytes(writer.buffer))
                board = board_fragment()
                read_layer_stack(reader, board)
                read_length_rules(reader, board)
                self.assertEqual(reader.integer(), 17)
                self.assertEqual(reader.pos, len(reader.data))
                self.assertEqual(board['LayerStackName'], 'Two layer')
                core = board.one('LayerStackItems/LayerStackItem[2]')
                self.assertEqual(core['Lay'], -1)
                self.assertEqual(core.one('Material')['Name'], 'Core')
                self.assertTrue(core.one('Material')['VariableThickness'])
                self.assertEqual(board.one('Components/Component/Pattern/Pads/Pad[2]')['SignalDelay'], Decimal('.2'))
                self.assertTrue(board.one('MainLengthRule')['AnyError'])
                self.assertEqual(board.one('MainLengthRule/Rules/Rule')['Comp2'], 3)
                self.assertEqual(board.one('LengthRules/LengthRule')['Name'], 'Clock group')
                self.assertEqual(board.one('NetClasses/NetClass')['FixedLength'], 60)
                self.assertEqual(board.one('Tables/Table')['DocUnits'], 1)

    def test_camera_and_grid_extensions_replace_earlier_values(self):
        writer = stream(46)
        write_values(writer, 'number', .1234, -.5678, .6)
        writer.integer(4)
        writer.number(.9)
        writer.integer(17)
        root = Element('')
        root.add('Xpos', 0)
        root.add('Ypos', -1)
        board = root.append(board_fragment())
        reader = Reader(bytes(writer.buffer))
        read_camera_extension(reader, root)
        read_grid_extension(reader, board)
        self.assertEqual(root['Xpos'], Decimal('.1234'))
        self.assertEqual(root['Ypos'], Decimal('-.5678'))
        self.assertEqual(len(root.children('Xpos')), 1)
        self.assertEqual(board.one('Settings')['GridSize'], Decimal('.15'))
        self.assertEqual(board.one('Components/Component')['PlacementClearance'], Decimal('.9'))
        self.assertEqual(reader.integer(), 17)

    def test_mask_extensions_share_placed_and_cached_pad_state_vocabulary(self):
        board = board_fragment()
        for name in ('DRC', 'LastDRC'):
            board.add(name).add('LayClearances').add('LayClearance')
        definition = Element('Definition')
        cached_pad = definition.add('Pattern').add('Pads').add('Pad')
        pads = board.select('Components/Component/Pattern/Pads/Pad')+[cached_pad]
        names = ('DisableTopMask', 'DisableBottomMask', 'DisableTopPaste', 'DisableBottomPaste')
        for pad in pads:
            for name in names:
                pad.add(name, 0)
        writer = stream(45)
        write_values(writer, 'number', .3, .6)
        for _ in range(2):
            write_values(writer, 'boolean', True, False, True)
            write_values(writer, 'number', .1, .2, .3, .4)
        for _ in pads:
            write_values(writer, 'integer', 1, 2, 0, 1)
        writer.integer(17)
        reader = Reader(bytes(writer.buffer))
        read_mask_extensions(reader, board, (CachedDefinitionInput(definition, ()),))
        self.assertEqual(reader.integer(), 17)
        self.assertEqual(reader.pos, len(reader.data))
        for pad in pads:
            self.assertEqual([pad[name] for name in names], [1, 2, 0, 1])
            self.assertEqual(len(pad.children('DisableTopMask')), 1)
        self.assertEqual(board.one('DRC/LayClearances/LayClearance')['SameSmdToPad'], Decimal('.3'))
        self.assertTrue(board.one('LastDRC')['CheckSameComponentPads'])

    def test_meanders_extend_net_pair_and_removed_pair_geometry(self):
        board = board_fragment()
        net_points = board.one('Nets/Net').add('Traces').add('Trace').add('Points')
        net_points.add('Point')
        net_points.add('Point')
        for collection, kind in (('DifferentialPairs', 'DifferentialPair'), ('RemovedDifferentialPairs', 'RemovedDifferentialPair')):
            pair = board.add(collection).add(kind)
            center = pair.add('Segments').add('Segment').add('CenterPoints').add('CenterPoint')
            center.add('PosPoints').add('PosPoint')
            center.add('NegPoints').add('NegPoint')
            if kind == 'DifferentialPair':
                for side in ('Pos', 'Neg'):
                    pair.add(side+'SeparateTraces').add(side+'Trace').add('Points').add('Point')
        writer = stream(44)
        writer.number(.3)
        for _ in range(2):
            writer.integer(3)
            writer.number(45)
        for _ in range(2):
            writer.integer(2)
            writer.number(30)
            writer.boolean(True)
        for _ in range(2):
            writer.integer(4)
            writer.number(-30)
        for _ in range(2):
            writer.integer(1)
            writer.number(60)
            writer.boolean(False)
        writer.integer(17)
        reader = Reader(bytes(writer.buffer))
        read_meanders(reader, board)
        self.assertEqual(reader.integer(), 17)
        self.assertEqual(reader.pos, len(reader.data))
        self.assertEqual(board.one('Nets/Net')['MeanderGap'], Decimal('.3'))
        self.assertEqual(net_points.one('Point[2]')['MeanderAngle'], 45)
        self.assertEqual(board.one('DifferentialPairs/DifferentialPair/NegSeparateTraces/NegTrace/Points/Point')['MeanderAngle'], -30)
        self.assertEqual(board.one('RemovedDifferentialPairs/RemovedDifferentialPair/Segments/Segment/CenterPoints/CenterPoint/PosPoints/PosPoint')['Meander'], 1)

    def test_absent_revision_sections_consume_nothing(self):
        for version, functions in ((41, (read_camera_extension,)),
                                   (42, (read_layer_stack, read_length_rules)),
                                   (43, (read_meanders,)), (45, (read_grid_extension,))):
            for function in functions:
                with self.subTest(version=version, function=function.__name__):
                    writer = stream(version)
                    writer.integer(17)
                    reader = Reader(bytes(writer.buffer))
                    function(reader, board_fragment())
                    self.assertEqual(reader.integer(), 17)


if __name__ == '__main__':
    unittest.main()
