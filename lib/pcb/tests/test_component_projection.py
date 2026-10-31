"""PCB component output preserves current authored geometry and references."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.asc import dumps
from lib.common.asc_text import project_text
from lib.common.conversion import ConversionReport
from lib.common.model import Document, Element
from lib.common.schema import MISSING
from lib.pcb.formats.asc.component_projection import project_components
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.rule_projection import project_rules
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.errors import PcbError
from lib.pcb.formats.output_indices import OutputIndices, pad_number
from lib.pcb.formats.placement_frames import normalize_frames
from lib.pcb.model.objects import (new_document, new_component, new_pad, new_pattern_drawing,
                                   new_net, new_user_field, new_via_style)


def design():
    document = new_document()
    board = document.one('/Board')
    component = board.one('Components').append(new_component('Device', 'U1'))
    component['Value'] = 'Example'
    component.one('UserFields').append(new_user_field('Order', 'ABC'))
    pattern = component.one('Pattern')
    pattern['Name'] = 'Package'
    for index, number in enumerate(('1', '2')):
        pattern.one('Pads').append(new_pad(number, x=index*2, y=index))
    shape = pattern.one('Shapes').append(new_pattern_drawing(kind=8))
    shape['Layer'] = 2
    shape['TextAngle'] = Decimal('9.25')
    for point in ((-1, -2), (4, 6)):
        shape.one('Points_New').add('pt', *point)
    text = pattern.one('Shapes').append(new_pattern_drawing(kind=7))
    text['TextShow'] = 3
    text.one('Points_New').add('pt', 1, 2)
    net = board.one('Nets').append(new_net('Signal'))
    for pad in pattern.select('Pads/Pad'):
        pad['Net'] = net
    component['Layer'] = board.one('Layers/Layer[1]')
    via = board.one('ViaStyles').append(new_via_style('Through', size=2, hole_size=1))
    component['Via'] = via
    return document


def project_input(document, *, report=None):
    """Supply neutral net records while the independent net writer is pending."""
    source = document.one('/Board')
    syntax = Document(representation='asc')
    syntax.root.add('Source', 'DipTrace-PCBN', 62)
    syntax.root.add('Units', document.root['Units'])
    board = syntax.root.add('Board')
    board.append(project_components(source, report=report))
    nets = board.add('Nets')
    indices = OutputIndices(source)
    for source_net in source.select('Nets/Net'):
        net = nets.add('Net', source_net['Name'])
        net.add('Number', source_net['Number'])
        net.add('Enabled', 'Y')
        net.add('NetClass', indices.class_number(source_net['Class']))
        members = net.add('Component')
        for member in source_net.select('Pads/Item'):
            members.add('pt', member['ComponentIndex'], pad_number(member['Pad']))
        net.add('Lines')
    for row in tuple(project_rules(source).children()):
        row.move_to(board)
    return syntax


def reopen(document, *, report=None):
    return assemble_graphics(prepare_core(dumps(project_input(document, report=report), preserve=False))).document


def signature(component):
    result = {}
    for node in component.walk(include_self=True):
        if node.schema is None or not node.schema.fields:
            continue
        path = node.path.removeprefix(component.path)
        for name, field in node.schema.fields.items():
            if field.getter is None and node.child(name) is None and field.default is MISSING:
                continue
            current = node.get(name, None if field.default is MISSING else field.default)
            if field.kind == 'reference':
                current = None if current is None else current.path
            elif isinstance(current, tuple):
                current = tuple(tuple(part.path for part in item) if isinstance(item, tuple)
                                else item.path for item in current)
            result[path+'/'+name] = current
    return result


def component_text(document):
    document = document.clone()
    normalize_frames(document.one('/Board'))
    output = Document(representation='asc')
    output.root.append(project_components(document.one('/Board')))
    return dumps(output, preserve=False)


def assert_same(test, first, second):
    # Compare current meaning after the reader's physical-frame modernization.
    expected = second._owner().clone()
    normalize_frames(expected.one('/Board'))
    second = expected.one(second.path)
    a, b = signature(first), signature(second)
    test.assertEqual({name: (a.get(name), b.get(name)) for name in a.keys() | b.keys()
                      if name not in a or name not in b or a[name] != b[name]}, {})


class ComponentProjectionTests(unittest.TestCase):
    def test_shield_membership_is_typed_and_warns_when_asc_omits_it(self):
        document = design()
        component = document.one('/Board/Components/Component')
        self.assertEqual(component['ShieldGroup'], -1)
        component['ShieldGroup'] = 0
        report = ConversionReport()
        output = project_components(document.one('/Board'), report=report)
        self.assertIsNone(output.one('Component').child('ShieldGroup'))
        self.assertEqual([notice.rule for notice in report.warnings], ['component-shield-group'])
        self.assertEqual(component['ShieldGroup'], 0)
        with self.assertRaises(TypeError):
            component['ShieldGroup'] = 'unassigned'

    def test_current_component_footprint_and_indices_round_trip_without_a_layout_context(self):
        document = design()
        component = document.one('/Board/Components/Component')
        before = dumps(document, preserve=False)
        projected = project_input(document)
        part = projected.one('/Board/Components/Component')
        self.assertEqual(part.one('Pads/Pad[2]').values[:3], (1, '1', ''))
        self.assertEqual(part.one('Pads/Pad[2]/Number').values, (1,))
        self.assertEqual(len(part.one('Pads').children()), 4)
        headers = part.one('Shapes').children('Shape')
        self.assertEqual([row.values[0] for row in headers], [0, 8, 7, 0])
        self.assertTrue(all(row.values[3:9] == (0,)*6 for row in headers))
        self.assertEqual(part.one('Model3D/pt').values, (0, 0, 0, 0, 0, 0, 1, 1, 1, 'N', 'N', 0))
        imported = reopen(document)
        assert_same(self, imported.one('/Board/Components/Component'), component)
        self.assertEqual(dumps(document, preserve=False), before)
        self.assertEqual(component_text(imported), component_text(document))
        document.references.validate()
        imported.references.validate()

    def test_edits_reorder_and_bound_text_use_current_data(self):
        document = reopen(design())
        component = document.one('/Board/Components/Component')
        component['Value'] = 'Changed'
        component['RefDes'] = 'U12'
        component['X'], component['Angle'] = Decimal('8.75'), Decimal('17.25')
        pads = component.one('Pattern/Pads')
        first = pads.one('Pad[1]')
        first['PadAngle'] = Decimal('0.37')
        first.move_to(pads, 1)
        component.one('Pattern/Shapes/Shape[1]/Points_New/pt[1]')['X'] = Decimal('-3.5')
        imported = reopen(document).one('/Board/Components/Component')
        assert_same(self, imported, component)
        self.assertEqual(imported.one('Pattern/Shapes/Shape[2]/TextLine/pt')['Text'], 'Changed')
        self.assertEqual(imported.one('Pattern/Pads/Pad[2]')['StringNumber'], '1')
        self.assertEqual(imported['Angle'], Decimal('17.25'))

    def test_terminal_paste_thermal_layers_teardrops_and_model_placement_round_trip(self):
        document = design()
        component = document.one('/Board/Components/Component')
        component.one('Pattern')['PadShape'] = 3
        component.one('Pattern/PadPoints').add('pt', -2, 3)
        component.one('Pattern/PadPoints').add('pt', 4, 5)
        pad = component.one('Pattern/Pads/Pad[1]')
        terminal = pad.add('PadTerminal', 0)
        for name, current in dict(Type=3, X=1, Y=2, Angle=Decimal('.4'), ShapeWidth=3,
                                  ShapeHeight=4, ShapeCorner=5).items():
            terminal.add(name, current)
        terminal.add('ShapePoints').add('pt', 1, 2)
        pad.one('PadMask_TopSegments').add('pt', 1, 2, 3, 4)
        pad.one('PadPoints_New').add('pt', 5, 6)
        pad['PadShape_New'] = 3
        pad['DisableTopMask'] = 3
        hidden = pad.add('HideLayer').add('Item')
        hidden['Layer'] = document.one('/Board/Layers/Layer[2]')
        thermal = pad.add('CustomSpokes').add('CustomSpoke')
        thermal['Layer'] = document.one('/Board/Layers/Layer[1]')
        thermal['Type'], thermal['Spoke'], thermal['Width'] = 2, 4, Decimal('.3')
        pad.add('TeardropParams')['PadViaLength'] = Decimal('1.25')
        model = component.one('Pattern/Model3D')
        model['Type'], model['IPC_XOff'], model['KeepPins'] = 1, 2, True
        model.one('Rotate')['Z'] = Decimal('37.25')
        model.one('Offset')['X'] = Decimal('1.23')
        defaults = project_input(document).one('/Board/Components/Component/PadPoints')
        self.assertEqual([point.kind for point in defaults.children()], ['Type', 'Type'])
        imported = reopen(document).one('/Board/Components/Component')
        assert_same(self, imported, component)
        self.assertEqual(imported.one('Pattern/Model3D/Rotate')['Z'], Decimal('37.25'))

    def test_new_geometry_and_pad_settings_are_typed_and_invalid_attachment_is_atomic(self):
        document = design()
        component = document.one('/Board/Components/Component')
        points = component.one('Pattern/Shapes/Shape[1]/Points_New')
        with patch.object(document.root, 'walk', side_effect=AssertionError('global scan')):
            point = points.add('pt', 7, 8)
            self.assertEqual(point['X'], 7)
            point['Y'] = 9
            hidden = component.one('Pattern/Pads/Pad[1]').add('BlindLayer').add('Item')
            hidden['Layer'] = document.one('/Board/Layers/Layer[1]')
            self.assertEqual(hidden['Lay'], 0)
            count = len(points.children())
            invalid = Element('pt', 'bad', 0)
            with self.assertRaises((TypeError, ValueError)):
                points.append(invalid)
            self.assertEqual(len(points.children()), count)
            self.assertIsNone(invalid.parent)
        document.references.validate()

    def test_output_omissions_warn_and_leave_authored_data_intact(self):
        document = design()
        component = document.one('/Board/Components/Component')
        pad = component.one('Pattern/Pads/Pad[1]')
        pad['Id'] = 71
        shape = component.one('Pattern/Shapes/Shape[1]')
        shape['FontMono'] = True
        supplier = component.add('Suppliers')
        supplier['SourceLocator'] = 'catalog:part'
        supplier['MainSupplier'] = True
        supplier.add('Prices').add('Quote', 10, Decimal('1.25'))
        report = ConversionReport()
        project_components(document.one('/Board'), report=report)
        self.assertEqual({notice.rule for notice in report.warnings},
                         {'pad-persistent-key', 'pattern-font-monospace', 'supplier-details'})
        self.assertEqual(pad['Id'], 71)
        self.assertTrue(shape['FontMono'])
        imported = reopen(document, report=ConversionReport()).one('/Board/Components/Component/Suppliers')
        self.assertTrue(imported['MainSupplier'])
        self.assertEqual(supplier.one('Prices/Quote')['Price'], Decimal('1.25'))

    def test_text_restrictions_use_the_shared_asc_policy_on_the_output_view(self):
        document = design()
        component = document.one('/Board/Components/Component')
        component['Value'] = '2" Ω\nthird'
        output = project_input(document)
        report = ConversionReport()
        project_text(output, report=report)
        self.assertEqual(output.one('/Board/Components/Component/Value').values, ('2! O!third',))
        self.assertEqual({notice.rule for notice in report.warnings},
                         {'asc-text-sanitization', 'asc-text-encoding'})
        self.assertEqual(component['Value'], '2" Ω\nthird')

    def test_binary_paste_counts_are_consumed_without_discarding_segment_geometry(self):
        from lib.pcb.formats.assembly.assemble import assemble_core
        from lib.pcb.tests.test_core_assembly import fixture
        for count in (1, 2):
            data = fixture()
            segments = data.board.one('Components/Component/Pattern/PadMask_TopSegments')
            segments.set_values(count)
            segments.add('pt', 1, 2, 3, 4)
            if count == 2:
                with self.assertRaisesRegex(PcbError, 'paste segment count'):
                    assemble_core(data)
            else:
                component = assemble_core(data).document.one('/Board/Components/Component')
                current = component.one('Pattern/PadMask_TopSegments')
                self.assertEqual(current.arguments, ())
                self.assertEqual(current.one('pt').values, (1, 2, 3, 4))

    def test_footprint_shield_membership_warns_without_changing_the_source(self):
        document = design()
        component = document.one('/Board/Components/Component')
        pad = component.one('Pattern/Pads/Pad[1]')
        shape = component.one('Pattern/Shapes/Shape[1]')
        pad['ShieldGroup'], shape['ShieldGroup'] = 5, 6
        report = ConversionReport()
        output = project_components(document.one('/Board'), report=report)
        self.assertFalse(any(node.child('ShieldGroup') is not None for node in output.walk(include_self=True)))
        self.assertEqual({notice.rule for notice in report.warnings}, {'pad-shield-group', 'pattern-shield-group'})
        self.assertEqual((pad['ShieldGroup'], shape['ShieldGroup']), (5, 6))
        self.assertFalse(report.errors)

    def test_unmapped_fields_remain_explicit_instead_of_being_dropped(self):
        for location in ('component', 'pad', 'pattern extension'):
            document = design()
            component = document.one('/Board/Components/Component')
            if location == 'component':
                component.add('Unmapped', 1)
            elif location == 'pad':
                component.one('Pattern/Pads/Pad[1]').add('Unmapped', 1)
            else:
                component.one('Pattern').add('UserFields').add('Unmapped', 1)
            with self.subTest(location=location), self.assertRaises(PcbError):
                project_components(document.one('/Board'))


if __name__ == '__main__':
    unittest.main()
