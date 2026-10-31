"""Whole-object check targets do not invent vertex identities from unused slots."""
from decimal import Decimal
import unittest
from xml.etree import ElementTree

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.tests.test_dipxml_electrical import prepared
from lib.pcb.tests.test_drc_result_inputs import xml_source
from lib.pcb.tests.test_graphics import design as graphics_source


@import_diagnostics('dipxml')
def read_xml(text):
    return assemble_graphics(prepared(text)).document


class DrcUnusedSelectorTests(unittest.TestCase):
    def test_positive_unused_points_bind_whole_pads_drawings_and_teardrops(self):
        for kind, obj, sub, expected in (
            ('PadHole', 8, 17, '/Board/Components/Component/Pattern/Pads/Pad[1]'),
            ('Shape', 23, -1, '/Board/Shapes/Shape[1]'),
            ('Teardrop', 7, 77, '/Board/Nets/Net/Teardrops/Teardrop'),
        ):
            for point in (0, 999):
                with self.subTest(kind=kind, point=point):
                    source = ElementTree.fromstring(xml_source())
                    error = source.find('Board/DesignErrors/DesignError')
                    error.attrib.update(ObjectType1=kind, Object1=str(obj), SubObject1=str(sub), Point1=str(point))
                    report = ConversionReport()
                    document = read_xml(ElementTree.tostring(source, encoding='unicode'), report=report)
                    row = document.one('/Board/DesignErrors/DesignError')
                    self.assertIs(row['Target1'], document.one(expected))
                    self.assertEqual(row['Point1'], -1)
                    self.assertIsNone(row.child('Point1'))
                    self.assertEqual((row['Value'], row['Rule']), (Decimal('.3'), Decimal('.6')))
                    self.assertIn('unused-design-error-point', [n.rule for n in report.infos])
                    self.assertNotIn('unresolved-design-error-targets', [n.rule for n in report.warnings])
                    target = row['Target1']
                    document.copy(target, index=0)
                    self.assertIs(row['Target1'], target)
                    self.assertEqual(row['Point1'], -1)
                    document.references.validate()

    def test_component_holes_keep_identity_without_a_subfeature_model(self):
        @import_diagnostics('dip')
        def read(decoded):
            return assemble_graphics(decoded).document

        for mode in (5, 11):
            decoded, _, _ = graphics_source()
            row = decoded.board.add('DesignErrors').add('DesignError')
            for name, value in dict(ObjectType1=mode, Object1=41, SubObject1=1, Point1=99,
                                    Value=Decimal('.25'), Rule=Decimal('.5')).items():
                row.add(name, value)
            report = ConversionReport()
            document = read(decoded, report=report)
            current = document.one('/Board/DesignErrors/DesignError')
            self.assertIs(current['Target1'], document.one('/Board/Components/Component/Pattern/Holes/Hole'))
            self.assertEqual(current['Point1'], -1)
            self.assertEqual((current['Value'], current['Rule']), (Decimal('.25'), Decimal('.5')))
            self.assertIn('unused-design-error-point', [n.rule for n in report.infos])
            document.references.validate()

    def test_missing_whole_object_keeps_only_meaningful_unresolved_selectors(self):
        source = ElementTree.fromstring(xml_source())
        source.find('Board/DesignErrors/DesignError').attrib.update(
            ObjectType1='Shape', Object1='999', SubObject1='-1', Point1='999')
        report = ConversionReport()
        document = read_xml(ElementTree.tostring(source, encoding='unicode'), report=report)
        row = document.one('/Board/DesignErrors/DesignError')
        self.assertEqual(row.one('UnresolvedTarget1').values, (999, -1, -1, -1))
        self.assertIn('unresolved-design-error-targets', [n.rule for n in report.warnings])
        self.assertIn('unused-design-error-point', [n.rule for n in report.infos])


if __name__ == '__main__':
    unittest.main()
