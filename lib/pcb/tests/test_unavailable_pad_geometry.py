"""Unavailable copper data is a model value, not retained wire bookkeeping."""
import unittest

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.footprint_bounds import physical_bounds
from lib.common.footprint_objects import new_pad
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import FORMATS
from lib.pcb.tests.test_xml_via_masks import via_document, COMPONENT, PAD


def unavailable():
    document = via_document()
    document.one(COMPONENT)['Via'] = None
    pad = document.one(PAD)
    pad['PadWidth_New'], pad['PadHeight_New'] = None, None
    return document


class UnavailablePadGeometryTests(unittest.TestCase):
    def test_unavailable_sizes_roundtrip_through_every_output_profile(self):
        document = unavailable()
        before = model_text(document, preserve=False)
        for format, support in FORMATS.items():
            for version in support.write_versions:
                with self.subTest(format=format, version=version):
                    report = ConversionReport()
                    data = io.serialize(document, format=format, version=version, report=report)
                    rebuilt = io.parse(data, report=report)
                    pad = rebuilt.one(PAD)
                    self.assertEqual((pad['PadWidth_New'], pad['PadHeight_New']), (None, None))
                    self.assertIn('unavailable-pad-geometry', {item.rule for item in report.infos})
                    self.assertIsNone(physical_bounds(pads=(pad,)))
                    self.assertEqual(model_text(document, preserve=False), before)
                    rebuilt.validate()

    def test_selecting_a_style_supplies_dimensions_without_retaining_old_absence(self):
        document = unavailable()
        component = document.one(COMPONENT)
        style = document.one('/Board/ViaStyles/ViaStyle')
        component['Via'] = style
        pad = document.one(PAD)
        self.assertEqual((pad['PadWidth_New'], pad['PadHeight_New']), (style['Size'],)*2)
        style['Size'] = 3
        self.assertEqual((pad['PadWidth_New'], pad['PadHeight_New']), (3, 3))
        component['Via'] = None
        self.assertEqual((pad['PadWidth_New'], pad['PadHeight_New']), (3, 3))
        document.validate()

    def test_binary_and_ascii_keep_independent_partially_known_sizes(self):
        document = unavailable()
        document.one(PAD)['PadHeight_New'] = 2
        for format in ('dip', 'asc'):
            with self.subTest(format=format):
                rebuilt = io.parse(io.serialize(document, format=format, report=ConversionReport()),
                                   report=ConversionReport())
                pad = rebuilt.one(PAD)
                self.assertEqual((pad['PadWidth_New'], pad['PadHeight_New']), (None, 2))
                self.assertIsNone(physical_bounds(pads=(pad,)))
                rebuilt.validate()

    def test_shared_definition_constraints_are_not_relaxed_with_placed_pcb_data(self):
        with self.assertRaises(TypeError):
            new_pad()['PadWidth_New'] = None
        document = unavailable()
        self.assertTrue(document.one(PAD).schema.fields['PadWidth_New'].nullable)
        document.validate()


if __name__ == '__main__':
    unittest.main()
