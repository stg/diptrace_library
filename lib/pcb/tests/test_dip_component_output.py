"""Binary component sections keep current geometry separate from bookkeeping."""
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from lib.common.asc import dumps
from lib.common.font_codec import read_font_properties, write_font_properties
from lib.common.footprint_codec import read_pad_mask_states
from lib.common.model import Element
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.dip.components import read_base_components
from lib.pcb.formats.dip.modern import _placed_pattern
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.writer import Writer
from lib.pcb.formats.dip.write_components import (component_outputs,
    write_base_components, write_pad_mask_overrides, write_placed_extensions,
    component_font_records)
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_component_projection import design, project_input
from lib.pcb.tests.test_dimension_projection import dimension
from lib.pcb.tests.test_global_projection import design as hierarchy_design


def sections(document):
    """A test stream of owned sections, deliberately not a complete DIP file."""
    outputs = component_outputs(document.one('/Board'))
    writer = Writer()
    writer.header()
    write_base_components(writer, outputs)
    base_end = len(writer.buffer)
    write_pad_mask_overrides(writer, outputs)
    for output in outputs:
        write_placed_extensions(writer, output)
    write_font_properties(writer, component_font_records(outputs))
    return writer, base_end


def read_sections(document):
    writer, base_end = sections(document)
    reader, board = Reader(bytes(writer.buffer)+b'\0'), Element('Board')
    upgrades = read_base_components(reader, board, len(document.select('/Board/Components/Component')))
    if reader.pos != base_end:
        raise AssertionError('component base section boundary differs')
    for pad in board.select('Components/Component/Pattern/Pads/Pad'):
        read_pad_mask_states(reader, pad, extended=True)
    for component in board.select('Components/Component'):
        _placed_pattern(reader, component)

    def fonts():
        for component in board.select('Components/Component'):
            yield component, 'MarkingFontSize', None
            for collection, kind in (('Shapes', 'Shape'), ('Dimensions', 'Dimension')):
                for node in component.select('Pattern/'+collection+'/'+kind):
                    yield node, 'FontSize', 'FontMono'
    read_font_properties(reader, fonts())
    if reader.pos != len(writer.buffer):
        raise AssertionError('component current section boundary differs')
    return board.one('Components/Component'), upgrades[0], writer


class DipComponentOutputTests(unittest.TestCase):
    def test_current_geometry_angles_unicode_and_fonts_survive_compatibility_slots(self):
        document = design()
        component = document.one('/Board/Components/Component')
        component['Name'], component['RefDes'] = 'Device Ω', 'U12'
        component['Angle'], component['MarkingFontSize'] = Decimal('17.25'), Decimal('1.25')
        pattern = component.one('Pattern')
        pattern['Width'], pattern['Height'] = 12, 8
        pad = pattern.one('Pads/Pad[1]')
        pad['PadAngle'] = Decimal('.37')
        pad.move_to(pad.parent)
        shape = pattern.one('Shapes/Shape[2]')
        shape['TextShow'], shape['FontSize'], shape['FontMono'] = 0, Decimal('2.125'), True
        for line in tuple(shape.select('TextLine/pt')):
            line.detach()
        shape.one('TextLine').add('pt', 'literal Ω')
        shape.one('TextLine').add('pt', 'second line')
        before = dumps(document, preserve=False)
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('companion read')):
            rebuilt, upgrade, writer = read_sections(document)
        self.assertEqual(rebuilt.one('Name').values, ('Device Ω',))
        self.assertEqual(rebuilt.one('RefDes').values, ('U12',))
        self.assertEqual(rebuilt.one('Angle').values, (Decimal('17.25'),))
        self.assertEqual(rebuilt.one('MarkingFontSize').values, (Decimal('1.25'),))
        self.assertEqual([node.values[1] for node in rebuilt.select('Pattern/Pads/Pad')], ['', '2', '1', ''])
        self.assertEqual(rebuilt.one('Pattern/Pads/Pad[3]/PadAngle').values, (Decimal('.37'),))
        restored = rebuilt.one('Pattern/Shapes/Shape[3]')
        self.assertEqual([row.values[0] for row in restored.select('TextLine/pt')], ['literal Ω', 'second line'])
        self.assertEqual(restored.one('FontSize').values, (Decimal('2.125'),))
        self.assertEqual(restored.one('FontMono').values, (True,))
        self.assertEqual([row.values for row in rebuilt.select('Pattern/Shapes/Shape[2]/Points_New/pt')],
                         [(-1, -2), (4, 6)])
        self.assertEqual(len(upgrade.drawings), 4)
        self.assertEqual(writer.compatibility_changes, [])
        self.assertEqual(sections(document)[0].buffer, writer.buffer)
        self.assertEqual(dumps(document, preserve=False), before)
        document.references.validate()

    def test_zero_extent_and_bounded_compatibility_values_keep_current_points(self):
        for size in (0, Decimal('.0001')):
            document = design()
            pattern = document.one('/Board/Components/Component/Pattern')
            pattern['Width'], pattern['Height'] = size, size
            point = pattern.one('Shapes/Shape[1]/Points_New/pt[1]')
            point['X'], point['Y'] = 100, -100
            rebuilt, _, writer = read_sections(document)
            self.assertEqual(rebuilt.one('Pattern/Shapes/Shape[2]/Points_New/pt[1]').values, (100, -100))
            self.assertTrue(writer.compatibility_changes)

    def test_hierarchy_keys_and_internal_pad_pairs_follow_current_identities(self):
        document = hierarchy_design()
        component = document.one('/Board/Components/Component')
        block = document.one('/Board/HierarchySheets/HSheet[1]/UpdateIds/UId')
        block['Id'], component['HiddenId'] = 104, 80
        first, second = component.select('Pattern/Pads/Pad')
        pair = component.one('IntConRecords').add('Item')
        pair['Pad1'], pair['Pad2'] = first, second
        policy = component.one('InternalConnections').add('IntCon')
        policy['Pad'], policy['ConnectAll'] = first, True
        first.move_to(first.parent)
        before = dumps(document, preserve=False)
        rebuilt, _, _ = read_sections(document)
        self.assertEqual([row.values for row in rebuilt.select('HierarchyPath/Item')], [(104,), (107,), (80,)])
        self.assertEqual(rebuilt.one('InternalConnection_Records/pt').values, (2, 1))
        self.assertEqual(rebuilt.one('InternalConnections/IntCon/ConnectAll').values, (True,))
        self.assertEqual([row.values for row in rebuilt.select('InternalConnections/IntCon/PadId/Item')], [(1,), (2,)])
        self.assertEqual([row.one('NetNumber').values[0] for row in rebuilt.select('Pattern/Pads/Pad')], [-1, 0, 0, -1])
        self.assertEqual(dumps(document, preserve=False), before)
        document.references.validate()

    def test_mask_states_terminals_thermal_layers_holes_and_model_settings(self):
        document = design()
        component = document.one('/Board/Components/Component')
        pattern = component.one('Pattern')
        pad = pattern.one('Pads/Pad[1]')
        pad['DisableTopMask'] = 3
        pad['PadHole'], pad['PadHoleH'] = Decimal('.8'), Decimal('1.2')
        terminal = pad.add('PadTerminal', 0)
        for name, value in dict(Type=3, X=1, Y=2, Angle=Decimal('.4'), ShapeWidth=3,
                                ShapeHeight=4, ShapeCorner=5).items():
            terminal[name] = value
        terminal.add('ShapePoints').add('pt', 1, 2)
        pad.one('PadMask_TopSegments').add('pt', 1, 2, 3, 4)
        hidden = pad.add('HideLayer').add('Item')
        hidden['Layer'] = document.one('/Board/Layers/Layer[2]')
        thermal = pad.add('CustomSpokes').add('CustomSpoke')
        thermal['Layer'] = document.one('/Board/Layers/Layer[1]')
        thermal['Type'], thermal['Spoke'], thermal['Width'] = 2, 4, Decimal('.3')
        pattern.one('Holes').add('Hole', True, False, 1, 2, 3, 4, -1)
        model = pattern.one('Model3D')
        model['Model3DFile'], model['IPC_XOff'] = 'package.step', Decimal('1.25')
        model.one('Rotate')['Z'] = Decimal('37.25')
        rebuilt, _, _ = read_sections(document)
        pad = rebuilt.one('Pattern/Pads/Pad[2]')
        self.assertEqual(pad.one('DisableTopMask').values, (3,))
        self.assertEqual(pad.one('PadHoleH').values, (Decimal('1.2'),))
        self.assertEqual(pad.one('PadTerminal/Angle').values, (Decimal('.4'),))
        self.assertEqual(pad.one('PadTerminal/ShapePoints/pt').values, (1, 2))
        self.assertEqual(pad.one('PadMask_TopSegments/pt').values, (1, 2, 3, 4))
        self.assertEqual(pad.one('HideLayer/Item').values, (1,))
        self.assertEqual(pad.one('CustomSpokes/CustomSpoke').values, (0, 2, 4, Decimal('.3')))
        self.assertEqual(rebuilt.one('Pattern/Holes/Hole[2]').values, (True, False, 1, 2, 3, 4, -1))
        self.assertEqual(rebuilt.one('Pattern/Model3D/Rotate/Z').values, (Decimal('37.25'),))
        self.assertEqual(rebuilt.one('Pattern/Model3D/IPC_XOff').values, (Decimal('1.25'),))

    def test_local_dimension_selectors_follow_reordered_pad_identities(self):
        source = project_input(design())
        row = dimension(source.one('/Board/Components/Component/Dimensions'), Connected1=0,
                        Object1=0, SubObject1=1, Point1=0, Connected2=-1, Layer=13, Group=-1)
        row.one('NonSignal').detach()
        row.one('PanelExclude').detach()
        document = assemble_graphics(prepare_core(dumps(source, preserve=False))).document
        document.one('/Board/Components/Component/Pattern/Pads/Pad[1]').move_to(
            document.one('/Board/Components/Component/Pattern/Pads'))
        rebuilt, _, _ = read_sections(document)
        dimension_record = rebuilt.one('Pattern/Dimensions/Dimension')
        self.assertEqual(dimension_record.one('SubObject1').values, (2,))
        self.assertEqual(dimension_record.one('FontSize').values, (Decimal('1.25'),))
        self.assertEqual(dimension_record.one('X1').values, (Decimal('.5'),))
        document.references.validate()

    def test_generated_text_marker_is_distinct_from_nontext_generated_flag(self):
        document = design()
        shapes = document.select('/Board/Components/Component/Pattern/Shapes/Shape')
        for shape in shapes:
            shape['MarkingGenerated'] = True
        rebuilt, upgrade, _ = read_sections(document)
        self.assertEqual([item.text_marker for item in upgrade.drawings], [False, False, True, False])
        self.assertEqual([row.one('Type').values[0] for row in rebuilt.select('Pattern/Shapes/Shape')], [0, 8, 7, 0])
        self.assertEqual([row.one('MarkingGenerated').values[0] for row in rebuilt.select('Pattern/Shapes/Shape')],
                         [False, True, True, False])

    def test_unmapped_owned_content_rejects_without_source_changes(self):
        for path in ('/Board/Components/Component', '/Board/Components/Component/Pattern/Pads/Pad[1]',
                     '/Board/Components/Component/Pattern'):
            document = design()
            document.one(path).add('Unmapped', 9)
            before = dumps(document, preserve=False)
            with self.subTest(path=path), self.assertRaises(PcbError):
                sections(document)
            self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
