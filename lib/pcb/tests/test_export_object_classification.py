"""Edited physical objects export through current classifications and links."""
import unittest
from unittest.mock import patch

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.formats.export_view import prepare_export
from lib.pcb.model.objects import new_net, new_pattern_drawing, new_user_field
from lib.pcb.tests.test_footprint_frames import world_pads
from lib.pcb.tests.test_xml_via_masks import via_document, COMPONENT, PAD


def add_drawing(document, kind=8):
    shape = document.one(COMPONENT+'/Pattern/Shapes').append(new_pattern_drawing(kind=kind))
    for point in ((10, 0), (12, 0)) if kind != 7 else ((100, 200),):
        shape.one('Points_New').add('pt', *point)
    if kind == 7:
        shape.one('TextLine').add('pt', 'Annotation')
    return shape


def state(document):
    return model_text(document, preserve=False), tuple(document.references)


class ExportObjectClassificationTests(unittest.TestCase):
    def test_compound_via_exports_all_profiles_without_losing_geometry_or_style_identity(self):
        document = via_document()
        component = document.one(COMPONENT)
        component['Angle'] = 0  # Isolate classification from binary scalar quantization.
        pad = document.one(PAD)
        pad['Net'] = document.one('/Board/Nets').append(new_net('Route'))
        add_drawing(document)
        document.validate()
        expected = world_pads(document)
        before = state(document)
        for format, support in FORMATS.items():
            for version in support.write_versions:
                with self.subTest(format=format, version=version):
                    report = ConversionReport()
                    rebuilt = io.parse(io.serialize(document, format=format, version=version, report=report),
                                       report=report)
                    current = rebuilt.one(COMPONENT)
                    current_pad = rebuilt.one(PAD)
                    self.assertEqual(current.one('Pattern')['Type'], 0)
                    self.assertEqual(len(current.select('Pattern/Shapes/Shape')), 1)
                    self.assertIs(current['Via'], rebuilt.one('/Board/ViaStyles/ViaStyle'))
                    self.assertIs(current_pad['Net'], rebuilt.one('/Board/Nets/Net'))
                    self.assertEqual(current_pad['Net']['Name'], 'Route')
                    for actual, original in zip(world_pads(rebuilt), expected):
                        for x, y in zip(actual, original):
                            self.assertAlmostEqual(x, y, places=12)
                    self.assertGreater(current.one('Pattern')['Width'], current['Via']['Size'])
                    self.assertFalse(rebuilt.references.manages(current_pad.one('PadWidth_New')))
                    old_size = current_pad['PadWidth_New']
                    current['Via']['Size'] = 5
                    self.assertEqual(current_pad['PadWidth_New'], old_size)
                    rebuilt.validate()
                    self.assertIn('standalone-object-normalization', {item.rule for item in report.infos})
                    self.assertEqual(state(document), before)
        self.assertEqual(component.one('Pattern')['Type'], 16)
        self.assertTrue(document.references.manages(pad.one('PadWidth_New')))
        component['Via']['Size'] = 3
        self.assertEqual(pad['PadWidth_New'], 3)
        document.validate()

    def test_text_does_not_turn_a_via_into_a_compound_object(self):
        document = via_document()
        add_drawing(document, kind=7)
        for format in FORMATS:
            with self.subTest(format=format):
                rebuilt = io.parse(io.serialize(document, format=format, report=ConversionReport()),
                                   report=ConversionReport())
                self.assertEqual(rebuilt.one(COMPONENT+'/Pattern')['Type'], 16)
                self.assertEqual(rebuilt.one(COMPONENT+'/Pattern/Shapes/Shape/TextLine/pt')['Text'], 'Annotation')
                self.assertTrue(rebuilt.references.manages(rebuilt.one(PAD+'/PadWidth_New')))
                rebuilt.validate()

    def test_binary_placement_quantization_does_not_accumulate_after_reclassification(self):
        document = via_document()
        add_drawing(document)
        original = world_pads(document)
        current = io.parse(io.serialize(document, format='dip', report=ConversionReport()),
                           report=ConversionReport())
        settled = world_pads(current)
        # Only the compensated component coordinates need rounding here. Each
        # binary number has a 0.0001 step, hence half a step of nearest rounding.
        for actual, initial in zip(settled, original):
            for x, y in zip(actual, initial):
                self.assertLessEqual(abs(x-y), .00005)
        for _ in range(3):
            current = io.parse(io.serialize(current, format='dip', report=ConversionReport()),
                               report=ConversionReport())
            self.assertEqual(world_pads(current), settled)
            current.validate()

    def test_removing_geometry_does_not_restore_a_historical_via_classification(self):
        document = via_document()
        add_drawing(document)
        current = io.parse(io.serialize(document, format='dip', report=ConversionReport()),
                           report=ConversionReport())
        current.remove(current.one(COMPONENT+'/Pattern/Shapes/Shape'))
        for format in FORMATS:
            with self.subTest(format=format):
                rebuilt = io.parse(io.serialize(current, format=format, report=ConversionReport()),
                                   report=ConversionReport())
                self.assertEqual(rebuilt.one(COMPONENT+'/Pattern')['Type'], 14)
                self.assertFalse(rebuilt.references.manages(rebuilt.one(PAD+'/PadWidth_New')))
                rebuilt.validate()

    def test_receiver_marking_initialization_is_a_warning_on_the_detached_view(self):
        document = via_document()
        component = document.one(COMPONENT)
        component['RefDes_SilkShow'], component['RefDes_SilkX'] = 1, 7
        user = component.one('UserFields').append(new_user_field('Order', 'ABC'))
        user['SilkShow'], user['SilkX'] = 1, 8
        before = state(document)
        for format in FORMATS:
            with self.subTest(format=format):
                report = ConversionReport()
                view, _ = prepare_export(document, destination=format, report=report)
                self.assertEqual(view.one(COMPONENT)['RefDes_SilkShow'], 2)
                self.assertEqual(view.one(COMPONENT)['RefDes_SilkX'], 7)
                field = view.one(COMPONENT+'/UserFields/UserField')
                self.assertEqual((field['SilkShow'], field['SilkX'], field['Value']), (2, 8, 'ABC'))
                self.assertIn('standalone-marking-visibility', {item.rule for item in report.warnings})
                self.assertEqual(state(document), before)
                view.validate()

    def test_failed_export_preserves_source_classification_and_managed_properties(self):
        document = via_document()
        add_drawing(document)
        before = state(document)
        with patch('lib.pcb.formats.dipxml.write.project_document', side_effect=RuntimeError('probe')):
            with self.assertRaisesRegex(RuntimeError, 'probe'):
                io.serialize(document, format='dipxml', report=ConversionReport())
        self.assertEqual(state(document), before)
        self.assertEqual(document.one(COMPONENT+'/Pattern')['Type'], 16)
        self.assertTrue(document.references.manages(document.one(PAD+'/PadWidth_New')))
        document.validate()


if __name__ == '__main__':
    unittest.main()
