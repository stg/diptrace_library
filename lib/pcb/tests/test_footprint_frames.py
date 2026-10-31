"""Footprint modernization preserves physical placement, links and stable data."""
from decimal import Decimal, localcontext
import math
import unittest
from xml.etree import ElementTree as ET

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.footprint_bounds import physical_bounds
from lib.common.geometry import transform_point
from lib.common.references import Property
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.formats.import_context import ImportContext
from lib.pcb.formats.placement_frames import normalize_frames
from lib.pcb.tests.test_dipxml_library import source
from lib.pcb.tests.test_xml_via_masks import via_document


COMPONENT = '/Board/Components/Component'
PATTERN = COMPONENT+'/Pattern'


def plain_xml():
    root = ET.fromstring(source())
    pattern = root.find('Library/Library/Patterns/Pattern')
    pattern.remove(pattern.find('Shapes'))
    for pad, x in zip(pattern.findall('Pads/Pad'), ('-1', '1')):
        pad.set('X', x)
        pad.set('Y', '0')
    component = root.find('Board/Components/Component')
    component.set('Side', 'Top')
    component.set('Angle', '0')
    return root


def plain():
    return io.parse(ET.tostring(plain_xml()), report=ConversionReport())


def world_pads(document):
    component = document.one(COMPONENT)
    return [transform_point((pad['X'], pad['Y']), origin=(component['X'], component['Y']),
                            angle=component['Angle']) for pad in component.select('Pattern/Pads/Pad')]


class FootprintFrameTests(unittest.TestCase):
    def test_local_reframing_keeps_board_geometry_and_reference_identity(self):
        document = plain()
        component = document.one(COMPONENT)
        component['Angle'] = Decimal('.37')
        pads = component.select('Pattern/Pads/Pad')
        for pad in pads:
            pad['X'] += 5
            pad['Y'] -= 2
        physical = world_pads(document)
        net = pads[0]['Net']
        refs = tuple(document.references)
        normalize_frames(document.one('/Board'))
        for actual, expected in zip(world_pads(document), physical):
            for value, original in zip(actual, expected):
                self.assertAlmostEqual(value, original, places=12)
        self.assertIs(pads[0]['Net'], net)
        self.assertEqual(tuple(document.references), refs)
        box = physical_bounds(pads=pads)
        self.assertEqual(box.center, (0, 0))
        self.assertEqual((component.one('Pattern')['Width'], component.one('Pattern')['Height']),
                         (Decimal('9.6'), Decimal('7.2')))
        normalized = model_text(document, preserve=False)
        normalize_frames(document.one('/Board'))
        self.assertEqual(model_text(document, preserve=False), normalized)
        document.validate()

    def test_small_center_shift_is_compensated_without_a_rounding_cutoff(self):
        document = plain()
        for pad in document.select(PATTERN+'/Pads/Pad'):
            pad['X'] += Decimal('.0005')
        normalize_frames(document.one('/Board'))
        self.assertEqual(document.one(COMPONENT)['X'], Decimal('30.0005'))
        self.assertEqual([pad['X'] for pad in document.select(PATTERN+'/Pads/Pad')], [-3, 3])
        self.assertEqual(document.one(PATTERN)['OriginX'], Decimal('-.0005'))
        before = model_text(document, preserve=False)
        normalize_frames(document.one('/Board'))
        self.assertEqual(model_text(document, preserve=False), before)

    def test_xml_constructs_template_frame_before_reading_placement_and_markings(self):
        root = plain_xml()
        pattern = root.find('Library/Library/Patterns/Pattern')
        for pad in pattern.findall('Pads/Pad'):
            pad.set('X', '3')
        ET.SubElement(pattern, 'Origin', X='1', Y='0')
        component = root.find('Board/Components/Component')
        component.set('Side', 'Bottom')
        document = io.parse(ET.tostring(root), report=ConversionReport())
        self.assertEqual(document.one(COMPONENT)['X'], 30)
        self.assertEqual(document.one(COMPONENT)['RefDes_SilkX'], 3)
        self.assertEqual(document.one(PATTERN)['OriginX'], 6)
        self.assertEqual([pad['X'] for pad in document.select(PATTERN+'/Pads/Pad')], [0, 0])
        cached = document.one('/Board/CacheLib/Slots/Slot/Definition/Pattern')
        self.assertEqual((cached['OriginX'], cached.one('Pads/Pad[1]')['X']), (3, 9))

    def test_only_explicit_position_markings_translate(self):
        document = plain()
        component = document.one(COMPONENT)
        component['RefDes_SilkAlign'] = 8
        component['RefDes_SilkX'] = 13
        component['Name_SilkAlign'] = 7
        component['Name_SilkX'] = 23
        offset = component.one('Pattern/Model3D/Offset')['X']
        for pad in component.select('Pattern/Pads/Pad'):
            pad['X'] += 5
        normalize_frames(document.one('/Board'))
        self.assertEqual((component['RefDes_SilkX'], component['Name_SilkX']), (8, 23))
        self.assertEqual(component.one('Pattern/Model3D/Offset')['X'], offset)

    def test_batch_translation_keeps_managed_coordinate_projections_coherent(self):
        document = plain()
        first, second = document.select(PATTERN+'/Pads/Pad')
        first['X'] = second['X'] = 5
        document.references.bind(second, first, Property(second.one('X'), 'X'), role='coordinate-copy')
        normalize_frames(document.one('/Board'))
        self.assertEqual((first['X'], second['X'], document.one(COMPONENT)['X']), (0, 0, 35))
        first['X'] = 2
        self.assertEqual(second['X'], 2)
        document.validate()

    def test_export_normalizes_a_detached_view_in_every_output_profile(self):
        document = plain()
        for pad in document.select(PATTERN+'/Pads/Pad'):
            pad['X'] += Decimal('1.5')
        physical = world_pads(document)
        before = model_text(document, preserve=False), tuple(document.references)
        for format, support in FORMATS.items():
            for version in support.write_versions:
                with self.subTest(format=format, version=version):
                    report = ConversionReport()
                    rebuilt = io.parse(io.serialize(document, format=format, version=version, report=report),
                                       report=report)
                    self.assertEqual(world_pads(rebuilt), physical)
                    self.assertEqual(rebuilt.one(COMPONENT)['X'], Decimal('31.5'))
                    self.assertIn('footprint-frame-normalization', {item.rule for item in report.infos})
                    again = io.parse(io.serialize(rebuilt, format=format, version=version,
                                                  report=ConversionReport()), report=ConversionReport())
                    self.assertEqual(world_pads(again), physical)
                    self.assertEqual((model_text(document, preserve=False), tuple(document.references)), before)
                    rebuilt.validate()

    def test_style_controlled_via_stays_coherent_after_recentering(self):
        document = via_document()
        component = document.one(COMPONENT)
        component.one('Pattern/Pads/Pad')['X'] = 2
        component['Angle'] = math.pi/2
        physical = world_pads(document)
        normalize_frames(document.one('/Board'))
        self.assertEqual(world_pads(document), physical)
        self.assertEqual(component.one('Pattern')['OriginX'], 0)
        component['Via']['Size'] = 3
        self.assertEqual(component.one('Pattern')['Width'], 3)
        document.validate()

    def test_common_fiducial_fallback_is_optional_and_stored_setting_wins(self):
        root = plain_xml()
        def read(context):
            return io.parse(ET.tostring(root), context=context, report=ConversionReport())
        hidden = ImportContext(show_component_fiducials=False)
        self.assertFalse(read(hidden).one('/Board/Settings')['ShowCompFiducials'])
        settings = ET.SubElement(root.find('Board'), 'Settings')
        selected = ET.SubElement(settings, 'ShowCompFiducials')
        selected.text = 'Y'
        self.assertTrue(read(hidden).one('/Board/Settings')['ShowCompFiducials'])
        selected.text = 'N'
        self.assertFalse(read(ImportContext()).one('/Board/Settings')['ShowCompFiducials'])
        with self.assertRaises(TypeError):
            ImportContext(show_component_fiducials=1)

    def test_fiducial_visibility_changes_the_body_envelope_without_moving_pads(self):
        for common, mode, kind, center, width in (
            (False, 0, 0, '-3', '3.6'),
            (True, 0, 0, '47.85', '105.3'),
            (False, 1, 0, '47.85', '105.3'),
            (True, 2, 0, '-3', '3.6'),
            (False, 2, 20, '47.85', '105.3'),
        ):
            with self.subTest(common=common, mode=mode, kind=kind):
                document = plain()
                component = document.one(COMPONENT)
                component['ShowFiducial'] = mode
                pattern = component.one('Pattern')
                pattern['Type'] = kind
                fiducial = pattern.one('Pads/Pad[2]')
                for name, value in dict(PadShape_New=20, PadWidth_New=1, PadHeight_New=1, X=100).items():
                    fiducial[name] = value
                physical = world_pads(document)
                normalize_frames(document.one('/Board'), common_fiducials=common)
                self.assertEqual(component['X'], 30+Decimal(center))
                self.assertEqual(pattern['Width'], Decimal(width))
                for actual, expected in zip(world_pads(document), physical):
                    for value, original in zip(actual, expected):
                        self.assertAlmostEqual(value, original, places=12)
                document.validate()

    def test_reframing_is_independent_of_ambient_decimal_precision(self):
        document = plain()
        for pad in document.select(PATTERN+'/Pads/Pad'):
            pad['X'] = Decimal('12345678901234567890.0000000000000000000005')
        with localcontext() as context:
            context.prec = 6
            normalize_frames(document.one('/Board'))
        self.assertEqual(document.one(COMPONENT)['X'], Decimal('12345678901234567920.0000000000000000000005'))
        self.assertEqual([pad['X'] for pad in document.select(PATTERN+'/Pads/Pad')], [0, 0])
        document.validate()

    def test_xml_construction_preserves_individual_visibility_overrides(self):
        for common, mode in ((False, 0), (True, 0), (True, 2), (False, 1)):
            document = plain()
            component = document.one(COMPONENT)
            document.one('/Board/Settings')['ShowCompFiducials'] = common
            component['ShowFiducial'] = mode
            component['RefDes_SilkAlign'] = 8
            component['RefDes_SilkX'] = 7
            fiducial = component.one('Pattern/Pads/Pad[2]')
            for name, value in dict(PadShape_New=20, PadWidth_New=1, PadHeight_New=1, X=100).items():
                fiducial[name] = value
            normalize_frames(document.one('/Board'), common_fiducials=common)
            before = model_text(document, preserve=False), tuple(document.references)
            expected = world_pads(document)
            for version in FORMATS['dipxml'].write_versions:
                with self.subTest(common=common, mode=mode, version=version):
                    current = document
                    for _ in range(3):
                        current = io.parse(io.serialize(current, format='dipxml', version=version,
                                                       report=ConversionReport()), report=ConversionReport())
                        self.assertEqual(current.one(COMPONENT)['ShowFiducial'], mode)
                        self.assertEqual(current.one(COMPONENT)['RefDes_SilkX'], component['RefDes_SilkX'])
                        self.assertEqual(current.one(COMPONENT)['X'], component['X'])
                        for actual, original in zip(world_pads(current), expected):
                            for x, y in zip(actual, original):
                                self.assertAlmostEqual(x, y, places=12)
                        current.validate()
                    self.assertEqual((model_text(document, preserve=False), tuple(document.references)), before)


if __name__ == '__main__':
    unittest.main()
