"""XML library and placed geometry share identities across a side reflection."""
from decimal import Decimal
import math
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.references import Property
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.formats.dipxml.library_output import project_library
from lib.common.units import XmlUnits
from lib.pcb.tests.test_dipxml_library import source


COMPONENT = '/Board/Components/Component'
PATTERN = COMPONENT+'/Pattern'


def fixture(*, side='Bottom', flipped=True, horizontal=True, detailed=False):
    root = ET.fromstring(source())
    component = root.find('Board/Components/Component')
    component.set('Side', side)
    component.set('Flip', 'Y' if flipped else 'N')
    component.set('HorzFlip', 'Y' if horizontal else 'N')
    if detailed:
        pattern = root.find('Library/Library/Patterns/Pattern')
        ET.SubElement(pattern, 'Origin', X='1.2', Y='2.3')
        style = root.find('Library/Library/PadStyles/PadStyle')
        style.set('Type', 'Through')
        style.set('Hole', '0.6')
        stack = style.find('MainStack')
        stack.set('Shape', 'Polygon')
        stack.set('XOff', '0.4')
        stack.set('YOff', '0.7')
        points = ET.SubElement(stack, 'Points')
        for x, y in (('1', '2'), ('3', '4'), ('-1', '-2')):
            ET.SubElement(points, 'Item', X=x, Y=y)
        terminal = ET.SubElement(ET.SubElement(style, 'Terminals'), 'Terminal',
                                 X='0.2', Y='0.3', Angle='0.25', Shape='Polygon', Width='1', Height='2')
        points = ET.SubElement(terminal, 'Points')
        ET.SubElement(points, 'Item', X='1', Y='2')
        ET.SubElement(points, 'Item', X='-1', Y='-2')
        masks = ET.SubElement(component.find('Pads/Pad'), 'MaskPaste', TopPaste='Segments')
        ET.SubElement(ET.SubElement(masks, 'TopSegments'), 'Item', X1='0.2', Y1='0.3', X2='0.7', Y2='0.4')
        shape = ET.SubElement(pattern.find('Shapes'), 'Shape', Id='18', Type='Text', Layer='Top Silk',
                              HorzAlign='Right', VertAlign='Bottom', TextAlign='Left', Angle='0.5')
        ET.SubElement(ET.SubElement(shape, 'Points'), 'Item', X='-3', Y='5')
        ET.SubElement(ET.SubElement(shape, 'Lines'), 'Item').text = 'Authored text'
        ET.SubElement(ET.SubElement(pattern, 'Holes'), 'Hole', Id='5', X='2', Y='3', Diam='1.5', HoleDiam='0.7')
        ET.SubElement(ET.SubElement(pattern, 'Dimensions'), 'Dimension', Id='6', Type='Free',
                      X1='1', Y1='2', X2='3', Y2='4', XD='5', YD='6')
    return ET.tostring(root, encoding='unicode')


def read(text):
    return io.parse(text, report=ConversionReport())


def geometry(pattern):
    return dict(origin=(pattern['OriginX'], pattern['OriginY']),
        pads=[(pad['X'], pad['Y'], pad['PadShape_X'], pad['PadShape_Y'], pad['PadAngle'],
               [row.values for row in pad.select('PadPoints_New/pt')],
               [(terminal['X'], terminal['Y'], terminal['Angle'],
                 [row.values for row in terminal.select('ShapePoints/pt')])
                for terminal in pad.children('PadTerminal')],
               [row.values for row in pad.select('PadMask_TopSegments/pt')]) for pad in pattern.select('Pads/Pad')],
        shapes=[(shape['Type'], [row.values for row in shape.select('Points_New/pt')],
                 shape.get('TextHorz', 0), shape.get('TextAngle', 0), shape.get('TextAlign', 0))
                for shape in pattern.select('Shapes/Shape') if not shape.get('MarkingGenerated', False)],
        holes=[(hole['X'], hole['Y']) for hole in pattern.select('Holes/Hole')],
        dimensions=[tuple(row[name] for name in ('X1', 'Y1', 'X2', 'Y2', 'XD', 'YD'))
                    for row in pattern.select('Dimensions/Dimension')])


class XmlPlacementFrameTests(unittest.TestCase):
    def test_cached_and_placed_paste_sides_remain_independent(self):
        cache_pad = '/Board/CacheLib/Slots/Slot/Definition/Pattern/Pads/Pad[1]'
        placed_pad = PATTERN+'/Pads/Pad[1]'

        def paste(pad):
            return pad['DisableTopPaste'], pad['DisableBottomPaste'], pad['PadMask_Percent']

        for side in ('Top', 'Bottom'):
            document = read(fixture(side=side, flipped=False, horizontal=False))
            template, placement = document.one(cache_pad), document.one(placed_pad)
            # A placed pad's board-side settings need not match the reusable
            # library definition, even when both use the same footprint name.
            template['DisableTopPaste'], template['DisableBottomPaste'] = 3, 0
            template['PadMask_Percent'] = 40
            placement['DisableTopPaste'], placement['DisableBottomPaste'] = 0, 3
            placement['PadMask_Percent'] = 60
            before = model_text(document, preserve=False), tuple(document.references)
            for version in FORMATS['dipxml'].write_versions:
                with self.subTest(side=side, version=version):
                    data = io.serialize(document, format='dipxml', version=version,
                                        report=ConversionReport())
                    xml = ET.fromstring(data)

                    def xml_paste(pattern_key, *, pad_id=None, overlay=None):
                        pattern = next(p for p in xml.findall('Library/Library/Patterns/Pattern')
                                       if p.get('PatternStyle') == pattern_key)
                        pads = pattern.findall('Pads/Pad')
                        pad = pads[0] if pad_id is None else next(p for p in pads if p.get('Id') == pad_id)
                        style = next(p for p in xml.findall('Library/Library/PadStyles/PadStyle')
                                     if p.get('Name') == pad.get('Style'))
                        # Settings may come from the physical style or an
                        # explicit placement overlay. Check their effective
                        # values without requiring one output arrangement.
                        values = {'TopPaste': 'Common', 'BotPaste': 'Common', 'Segment_Percent': '50'}
                        for masks in (style.find('MaskPaste'), pad.find('MaskPaste'), overlay):
                            if masks is not None:
                                values.update(masks.attrib)
                        return values['TopPaste'], values['BotPaste'], Decimal(values['Segment_Percent'])

                    key = xml.find('Library/Components/Component/Part/Pattern').get('Style')
                    self.assertEqual(xml_paste(key), ('Segments', 'Common', 40))
                    component = xml.find('Board/Components/Component')
                    pad = component.find('Pads/Pad')
                    self.assertEqual(xml_paste(component.get('PatternStyle'), pad_id=pad.get('Id'),
                                               overlay=pad.find('MaskPaste')), ('Common', 'Segments', 60))
                    rebuilt = read(data)
                    self.assertEqual(paste(rebuilt.one(cache_pad)), (3, 0, 40))
                    self.assertEqual(paste(rebuilt.one(placed_pad)), (0, 3, 60))
                    again = read(io.serialize(rebuilt, format='dipxml', version=version,
                                              report=ConversionReport()))
                    self.assertEqual(paste(again.one(cache_pad)), (3, 0, 40))
                    self.assertEqual(paste(again.one(placed_pad)), (0, 3, 60))
                    again.one(placed_pad)['DisableBottomPaste'] = 2
                    self.assertEqual(paste(again.one(cache_pad)), (3, 0, 40))
                    again.references.validate()
                    self.assertEqual((model_text(document, preserve=False), tuple(document.references)), before)

    def test_nearly_equal_named_footprints_keep_independently_edited_pad_geometry(self):
        from lib.pcb.model.objects import new_document, new_component, new_pad, new_pattern_drawing

        document = new_document()
        components = document.one('/Board/Components')
        first = components.append(new_component('Device', 'U1'))
        pattern = first.one('Pattern')
        pattern['Name'], pattern['Type'] = 'Shared name', 5
        for number, x in (('1', 0), ('2', 3)):
            pad = pattern.one('Pads').append(new_pad(number, x=x))
            pad['PadWidth_New'], pad['PadHeight_New'], pad['PadShape_New'] = 3, 3, 2
        # Keep the envelope centered so the edited pad cannot become a common
        # translation of the whole footprint during import normalization.
        outline = pattern.one('Shapes').append(new_pattern_drawing(kind=1))
        for point in ((-12, -12), (12, 12)):
            outline.one('Points_New').add('pt', *point)
        second = first.clone()
        second['RefDes'], second['X'] = 'U2', 30
        second.one('Pattern/Pads/Pad[2]')['Y'] = Decimal('.0051')
        components.append(second)
        before = model_text(document, preserve=False)

        def pad_positions(model):
            return {component['RefDes']: [(component['X']+pad['X'], component['Y']+pad['Y'])
                    for pad in component.select('Pattern/Pads/Pad')]
                    for component in model.select(COMPONENT)}

        expected = pad_positions(document)
        for version in FORMATS['dipxml'].write_versions:
            with self.subTest(version=version):
                data = io.serialize(document, format='dipxml', version=version, report=ConversionReport())
                placed = ET.fromstring(data).findall('Board/Components/Component')
                self.assertEqual(len({component.get('PatternStyle') for component in placed}), 2)
                rebuilt = read(data)
                self.assertEqual(pad_positions(rebuilt), expected)
                rebuilt.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_side_controls_the_frame_without_reinterpreting_independent_flip_flags(self):
        for side in ('Top', 'Bottom'):
            for flipped in (False, True):
                for horizontal in (False, True):
                    with self.subTest(side=side, flipped=flipped, horizontal=horizontal):
                        document = read(fixture(side=side, flipped=flipped, horizontal=horizontal))
                        component = document.one(COMPONENT)
                        pad = component.one('Pattern/Pads/Pad[1]')
                        self.assertEqual(pad['X'], Decimal('2.4') if side == 'Top' else Decimal('-2.4'))
                        self.assertEqual((component['Flipped'], component['HorizontalFlip']), (flipped, horizontal))
                        self.assertEqual((component['X'], component['Y'], component['Angle']), (30, 60, Decimal('7.8')))
                        self.assertIs(pad['Net'], document.one('/Board/Nets/Net'))
                        rebuilt = read(io.serialize(document, format='dipxml', version=62, report=ConversionReport()))
                        self.assertEqual(geometry(rebuilt.one(PATTERN)), geometry(component.one('Pattern')))
                        self.assertEqual((rebuilt.one(COMPONENT)['Flipped'], rebuilt.one(COMPONENT)['HorizontalFlip']),
                                         (flipped, horizontal))
                        document.validate()

    def test_complete_reflection_preserves_templates_and_non_geometric_settings(self):
        document = read(fixture(detailed=True))
        pattern = document.one(PATTERN)
        pad = pattern.one('Pads/Pad[1]')
        # The physical envelope has center (4.2, 5.1) before reflection.
        self.assertEqual((pattern['OriginX'], pattern['OriginY']), (Decimal('.6'), Decimal('-1.8')))
        self.assertEqual((pad['PadShape_X'], pad['PadShape_Y']), (Decimal('-1.2'), Decimal('-2.1')))
        self.assertEqual(pad.one('PadPoints_New/pt[1]').values, (-3, -6))
        terminal = pad.one('PadTerminal')
        self.assertEqual((terminal['X'], terminal['Y']), (Decimal('-0.6'), Decimal('-0.9')))
        self.assertEqual(terminal['Angle'], Decimal(str(math.tau))-Decimal('.25'))
        self.assertEqual(terminal.one('ShapePoints/pt[1]').values, (-3, -6))
        self.assertEqual(pad.one('PadMask_TopSegments/pt').values,
                         (Decimal('-2.1'), Decimal('-0.9'), Decimal('-0.6'), Decimal('-1.2')))
        text = pattern.select('Shapes/Shape', where=lambda shape: shape['Type'] == 7)[0]
        self.assertEqual((text['TextHorz'], text['TextVert'], text['TextAlign']), (-1, 1, -1))
        self.assertEqual(text['TextAngle'], Decimal(str(math.tau))-Decimal('.5'))
        self.assertEqual(text.one('Points_New/pt').values, (Decimal('13.2'), Decimal('-9.9')))
        self.assertEqual(pattern.one('Holes/Hole')['X'], Decimal('-1.8'))
        dimension = pattern.one('Dimensions/Dimension')
        self.assertEqual(tuple(dimension[name] for name in ('X1', 'X2', 'XD')),
                         (Decimal('1.2'), Decimal('-4.8'), Decimal('-10.8')))
        template = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        self.assertEqual(template['OriginX'], Decimal('3.6'))
        self.assertEqual(template.one('Pads/Pad[1]')['X'], 3)
        self.assertEqual(pattern.one('Model3D/Offset')['X'], 3)
        self.assertEqual(document.one(COMPONENT)['RefDes_SilkX'], 3)
        document.validate()

    def test_export_projects_library_and_mask_overlays_without_touching_the_source(self):
        document = read(fixture(detailed=True))
        before = model_text(document, preserve=False), tuple(document.references)
        report = ConversionReport()
        output = ET.fromstring(io.serialize(document, format='dipxml', version=62, report=report))
        component = output.find('Board/Components/Component')
        style = component.get('PatternStyle')
        pattern = next(row for row in output.findall('Library/Library/Patterns/Pattern') if row.get('PatternStyle') == style)
        self.assertEqual(Decimal(pattern.find('Pads/Pad').get('X')), Decimal('-.4'))
        pad_style = pattern.find('Pads/Pad').get('Style')
        definition = next(row for row in output.findall('Library/Library/PadStyles/PadStyle') if row.get('Name') == pad_style)
        segment = definition.find('MaskPaste/TopSegments/Item')
        self.assertEqual((Decimal(segment.get('X1')), Decimal(segment.get('X2'))), (Decimal('.2'), Decimal('.7')))
        self.assertEqual((model_text(document, preserve=False), tuple(document.references)), before)
        document.references.validate()

    def test_via_mask_overlay_uses_the_same_frame_as_the_physical_styles(self):
        from lib.pcb.tests.test_xml_via_masks import via_document, configure, PAD
        document = via_document()
        configure(document.one(PAD))
        output = ET.fromstring(io.serialize(document, format='dipxml', version=62, report=ConversionReport()))
        segment = output.find('Board/Components/Component/Pads/Pad/MaskPaste/TopSegments/Item')
        self.assertEqual((Decimal(segment.get('X1')), Decimal(segment.get('X2'))),
                         (Decimal('-.0762'), Decimal('-.0254')))
        rebuilt = read(ET.tostring(output, encoding='unicode'))
        self.assertEqual(rebuilt.one(PAD+'/PadMask_TopSegments/pt').values,
                         document.one(PAD+'/PadMask_TopSegments/pt').values)

    def test_failed_projection_restores_the_original_coordinate_view(self):
        document = read(fixture(detailed=True))
        before = model_text(document, preserve=False), tuple(document.references)
        with patch('lib.pcb.formats.dipxml.pattern_output.project_drawing', side_effect=RuntimeError('probe')):
            with self.assertRaisesRegex(RuntimeError, 'probe'):
                io.serialize(document, format='dipxml', version=62, report=ConversionReport())
        self.assertEqual((model_text(document, preserve=False), tuple(document.references)), before)
        document.references.validate()

    def test_reflected_input_can_write_all_three_format_families(self):
        document = read(fixture())
        expected = geometry(document.one(PATTERN))
        for format, support in FORMATS.items():
            for version in support.write_versions:
                with self.subTest(format=format, version=version):
                    rebuilt = read(io.serialize(document, format=format, version=version, report=ConversionReport()))
                    self.assertEqual(geometry(rebuilt.one(PATTERN)), expected)
                    rebuilt.validate()

    def test_standalone_physical_projection_retains_graph_managed_coordinates(self):
        document = read(fixture())
        first, second = document.select(PATTERN+'/Pads/Pad')
        document.references.bind(second, first, Property(second.one('X'), 'X'), role='coordinate-copy')
        before = model_text(document, preserve=False), tuple(document.references)
        project_library(document.one('/Board'), units=XmlUnits('mm'),
                        physical=document.select(COMPONENT+'/Pattern'), report=ConversionReport())
        self.assertEqual((model_text(document, preserve=False), tuple(document.references)), before)
        document.references.validate()

    def test_every_xml_profile_preserves_geometry_and_repeated_conversion_is_stable(self):
        document = read(fixture(detailed=True))
        expected = geometry(document.one(PATTERN))
        before = model_text(document, preserve=False), tuple(document.references)
        for version in FORMATS['dipxml'].write_versions:
            with self.subTest(version=version):
                rebuilt = read(io.serialize(document, format='dipxml', version=version, report=ConversionReport()))
                self.assertEqual(geometry(rebuilt.one(PATTERN)), expected)
                again = read(io.serialize(rebuilt, format='dipxml', version=version, report=ConversionReport()))
                self.assertEqual(geometry(again.one(PATTERN)), expected)
                self.assertEqual((model_text(document, preserve=False), tuple(document.references)), before)
                rebuilt.validate()
                again.validate()


if __name__ == '__main__':
    unittest.main()
