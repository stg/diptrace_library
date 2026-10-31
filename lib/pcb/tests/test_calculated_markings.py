"""Absent calculated labels reconstruct without changing authored source data."""
from decimal import Decimal
import math
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.text.layout import TextLayout
from lib.common.text.vector import TextMetrics
from lib.pcb.formats import io
from lib.pcb.formats.asc.components import unpack_component
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.formats.export_context import ExportContext
from lib.pcb.formats.export_view import prepare_export
from lib.pcb.model.markings import NAMES, SIDES
from lib.pcb.model.objects import new_document, new_component, new_pattern_drawing, new_user_field


PART = '/Board/Components/Component'


def design(width=12, height=6):
    document = new_document()
    board = document.one('/Board')
    for name, value in dict(CompFontSize=3, CompFontName='Example font', PatternFontVector=True,
                            PatternFontWidth=-1, PatternFontScale=1).items():
        board[name] = value
    for name in NAMES:
        for side in SIDES:
            board[name+'_Global_'+side+'Show'] = 2
            board[name+'_Global_'+side+'Align'] = 7
    component = board.one('Components').append(new_component('Device', 'U1'))
    component['Value'] = '10k'
    pattern = component.one('Pattern')
    pattern['Name'] = 'Package'
    outline = pattern.one('Shapes').append(new_pattern_drawing(kind=2))
    for x, y in ((-width/2, -height/2), (width/2, height/2)):
        outline.one('Points_New').add('pt', x, y)
    return document, component


def enable(component, name='RefDes', side='Silk', *, alignment=2):
    component[name+'_'+side+'Show'] = 1
    component[name+'_'+side+'Align'] = alignment


def labels(document):
    return { (shape['TextShow'], shape['Layer']): shape
             for shape in document.select(PART+'/Pattern/Shapes/Shape')
             if shape['Type'] == 7 and shape.get('MarkingGenerated', False) }


def point(shape):
    return shape.one('Points_New/pt').values


def raw_asc_labels(data):
    source = io.parse_source(data, report=ConversionReport())
    for component in source.select('/Board/Components/Component'):
        unpack_component(component)
    return labels(source)


class CalculatedMarkingTests(unittest.TestCase):
    def test_absent_globals_show_only_refdes_and_explicit_choices_take_precedence(self):
        document = new_document()
        board = document.one('/Board')
        board.one('Components').append(new_component('Device', 'U1'))
        before = dumps(document, preserve=False)
        actual = raw_asc_labels(io.serialize(document, format='asc', report=ConversionReport()))
        self.assertEqual(set(actual), {(2, 0)})
        self.assertEqual(actual[2, 0].one('TextLine/pt').values, ('U1',))
        self.assertEqual(dumps(document, preserve=False), before)

        # Stored zero remains an explicit value. Missing output fallbacks must
        # neither hide that label nor override a stored Hide choice.
        board['Name_Global_SilkShow'] = 0
        board['Name_Global_SilkAlign'] = 0
        board['RefDes_Global_SilkShow'] = 2
        view, _ = prepare_export(document, destination='asc', report=ConversionReport())
        self.assertEqual(set(labels(view)), {(1, 0)})
        self.assertEqual(labels(view)[1, 0].one('TextLine/pt').values, ('Device',))
        self.assertEqual(view.one('/Board')['Name_Global_SilkShow'], 0)
        self.assertEqual(view.one('/Board')['Name_Global_SilkAlign'], 0)

    def test_actual_asc_contains_missing_text_and_explicit_unquantized_placement(self):
        document, component = design()
        enable(component)
        enable(component, 'Value', alignment=8)
        component['Value_SilkX'], component['Value_SilkY'] = Decimal('3.5'), Decimal('-4.25')
        component['Value_SilkAngle'] = Decimal('8.25')
        before, report = dumps(document, preserve=False), ConversionReport()
        actual = raw_asc_labels(io.serialize(document, format='asc', report=report))
        self.assertEqual(set(actual), {(2, 0), (3, 0)})
        self.assertEqual(point(actual[2, 0]), (0, -3))
        self.assertEqual(actual[2, 0].one('TextLine/pt').values, ('U1',))
        self.assertEqual(point(actual[3, 0]), (Decimal('3.5'), Decimal('-4.25')))
        self.assertEqual(actual[3, 0]['TextAngle'], Decimal('8.25'))
        self.assertEqual(actual[3, 0].one('TextLine/pt').values, ('10k',))
        self.assertIn('calculated-marking-geometry', {notice.rule for notice in report.infos})
        self.assertEqual(dumps(document, preserve=False), before)
        self.assertEqual(labels(document), {})

    def test_all_supported_outputs_and_repeated_cycles_are_stable(self):
        document, component = design()
        enable(component)
        enable(component, side='Assy', alignment=8)
        component['RefDes_AssyX'], component['RefDes_AssyY'] = 1, 2
        before = dumps(document, preserve=False)
        for format, capability in FORMATS.items():
            for version in capability.write_versions:
                with self.subTest(format=format, version=version):
                    data = io.serialize(document, format=format, version=version, report=ConversionReport())
                    first = io.parse(data, report=ConversionReport())
                    if format == 'dipxml':
                        self.assertEqual(labels(first), {})
                    else:
                        self.assertEqual(set(labels(first)), {(2, 0), (2, 1)})
                    second = io.serialize(first, format=format, version=version, report=ConversionReport())
                    rebuilt = io.parse(second, report=ConversionReport())
                    self.assertEqual(io.serialize(rebuilt, format=format, version=version,
                                                  report=ConversionReport()), second)
                    rebuilt.references.validate()
        self.assertEqual(dumps(document, preserve=False), before)

    def test_provided_calculation_and_literal_bound_text_are_not_replaced(self):
        for generated in (False, True):
            with self.subTest(generated=generated):
                document, component = design()
                enable(component)
                shape = new_pattern_drawing(kind=7)
                shape['TextShow'], shape['MarkingGenerated'], shape['FontSize'] = 2, generated, Decimal('7.5')
                shape.one('TextLine').add('pt', 'U1')
                shape.one('Points_New').add('pt', 99, 88)
                component.one('Pattern/Shapes').append(shape)
                before = dumps(document, preserve=False)
                view, _ = prepare_export(document, destination='asc', report=ConversionReport())
                actual = [s for s in view.select(PART+'/Pattern/Shapes/Shape') if s['Type'] == 7]
                self.assertEqual(len(actual), 1)
                self.assertEqual((point(actual[0]), actual[0]['FontSize']), ((99, 88), Decimal('7.5')))
                self.assertEqual(dumps(document, preserve=False), before)

    def test_blank_visible_values_take_their_automatic_slot_and_fonts_are_injected(self):
        document, component = design()
        board = document.one('/Board')
        board['PatternFontVector'] = False
        component['Value'], component['Manufacturer'] = '', 'Vendor'
        for name in ('RefDes', 'Name', 'Value', 'Manufacturer'):
            enable(component, name, alignment=7)
        calls = []

        def measure(text, family, size):
            calls.append((text, family, size))
            return TextMetrics(20, 9)

        context = ExportContext(text_layout=TextLayout(measure))
        view, resolved = prepare_export(document, context=context, destination='asc', report=ConversionReport())
        actual = labels(view)
        self.assertEqual(point(actual[2, 0]), (0, -3))
        self.assertEqual(point(actual[1, 0]), (0, 3))
        self.assertEqual(actual[3, 0].one('TextLine/pt').values, ('',))
        self.assertEqual(point(actual[3, 0]), (Decimal('6.3'), -3))
        self.assertEqual(point(actual[7, 0]), (Decimal('6.3'), Decimal('-1.65')))
        self.assertEqual(calls, [('', 'Example font', 25), ('Vendor', 'Example font', 25)])
        self.assertIs(resolved.text_layout, context.text_layout)
        self.assertEqual(labels(document), {})

    def test_tall_body_edges_sides_and_custom_font_share_current_settings(self):
        document, component = design(2, 20)
        component['RefDes'] = 'A_Long_Reference1'
        component['BottomSide'] = True
        component['CustomMarkingFont'], component['MarkingFontSize'] = True, Decimal('5.5')
        enable(component, alignment=7)
        enable(component, side='Assy', alignment=6)
        view, _ = prepare_export(document, destination='asc', report=ConversionReport())
        actual = labels(view)
        self.assertEqual(point(actual[2, 0]), (1, 0))
        self.assertEqual(actual[2, 0]['TextAngle'], Decimal(str(-math.pi/2)))
        self.assertEqual(point(actual[2, 1]), (-1, -10))
        self.assertEqual(actual[2, 0]['FontSize'], 5.5)
        self.assertEqual(actual[2, 1]['FontSize'], 5.5)

    def test_edge_choices_stay_local_under_arbitrary_component_rotation(self):
        expected = {
            1: ((0, 0), 0, 0, Decimal(str(math.pi/2))),
            2: ((0, -10), 0, 1, 0),
            3: ((0, 10), 0, -1, 0),
            4: ((-1, 0), 0, 1, Decimal(str(math.pi/2))),
            5: ((1, 0), 0, 1, Decimal(str(-math.pi/2))),
            6: ((1, -10), -1, 1, 0),
        }
        for alignment, values in expected.items():
            with self.subTest(alignment=alignment):
                document, component = design(2, 20)
                component['Angle'] = Decimal('8.25')
                enable(component, alignment=alignment)
                view, _ = prepare_export(document, destination='asc', report=ConversionReport())
                shape = labels(view)[2, 0]
                self.assertEqual((point(shape), shape['TextHorz'], shape['TextVert'], shape['TextAngle']), values)

    def test_custom_fields_generate_current_identity_bound_text(self):
        document, component = design()
        field = component.one('UserFields').append(new_user_field('Order', 'A42'))
        field['SilkShow'], field['SilkAlign'] = 1, 8
        field['SilkX'], field['SilkY'] = 7, 8
        view, _ = prepare_export(document, destination='asc', report=ConversionReport())
        shape = labels(view)[20, 0]
        self.assertEqual(point(shape), (7, 8))
        self.assertEqual(shape.one('TextLine/pt').values, ('A42',))
        view.one(PART+'/UserFields/UserField')['Value'] = 'Changed'
        self.assertEqual(shape.one('TextLine/pt').values, ('Changed',))
        self.assertEqual(field['Value'], 'A42')
        view.references.validate()

    def test_automatic_label_follows_explicit_placement_and_keeps_side_history_separate(self):
        cases = (
            (0, 1, 2, (0, -3)),
            (0, 1, -2, (0, 3)),
            (math.pi/2, 1, 2, (-6, 0)),
            (math.pi/2, -1, 2, (6, 0)),
            (math.acos(.69), 1, 2, (-6, 0)),
            (math.acos(.71), 1, 2, (0, -3)),
        )
        for mirrored in (False, True):
            for angle, x, y, expected in cases:
                with self.subTest(bottom=mirrored, angle=angle, x=x, y=y):
                    document, component = design()
                    component['BottomSide'] = mirrored
                    enable(component, 'Name', alignment=8)
                    component['Name_SilkX'], component['Name_SilkY'] = x, y
                    component['Name_SilkAngle'] = Decimal(str(angle))
                    enable(component, alignment=7)
                    enable(component, side='Assy', alignment=7)
                    before = dumps(document, preserve=False)
                    view, _ = prepare_export(document, destination='asc', report=ConversionReport())
                    actual = labels(view)
                    self.assertEqual(point(actual[1, 0]), (x, y))
                    self.assertEqual(actual[1, 0]['TextAngle'], Decimal(str(angle)))
                    self.assertEqual(point(actual[2, 0]), (-expected[0] if mirrored else expected[0], expected[1]))
                    self.assertEqual(point(actual[2, 1]), (0, -3))
                    self.assertEqual(dumps(document, preserve=False), before)

    def test_automatic_priority_covers_named_and_ordered_custom_fields(self):
        document, component = design()
        component['Manufacturer'], component['Datasheet'] = 'Maker', 'Document'
        for name in NAMES:
            enable(component, name, alignment=7)
        for name, value in (('Order', 'A'), ('Assembly', 'B')):
            field = component.one('UserFields').append(new_user_field(name, value))
            field['SilkShow'], field['SilkAlign'] = 1, 7
        view, _ = prepare_export(document, destination='asc', report=ConversionReport())
        actual = [shape for shape in view.select(PART+'/Pattern/Shapes/Shape') if shape['Type'] == 7]
        self.assertEqual([shape['TextShow'] for shape in actual], [2, 1, 3, 7, 4, 6, 20, 21])
        self.assertEqual([shape.one('TextLine/pt').values for shape in actual],
                         [('U1',), ('Device',), ('10k',), ('Maker',), ('Package',), ('Document',), ('A',), ('B',)])

    def test_missing_system_resources_keep_settings_with_reconstruction_info(self):
        document, component = design(2, 20)
        document.one('/Board')['PatternFontVector'] = False
        enable(component, alignment=7)
        report = ConversionReport()
        view, _ = prepare_export(document, destination='asc',
            context=ExportContext(text_layout=TextLayout()), report=report)
        self.assertEqual(labels(view), {})
        self.assertEqual(view.one(PART)['RefDes_SilkShow'], 1)
        self.assertIn('calculated-marking-font-resources', {notice.rule for notice in report.infos})
        self.assertFalse(report.warnings)
        self.assertFalse(report.errors)
        with self.assertRaises(TypeError):
            ExportContext(text_layout=object())


if __name__ == '__main__':
    unittest.main()
