"""Complete ASC composition uses current data and no retained input context."""
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.write import project
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.dipxml.read import prepare as prepare_xml
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import design as cache_design, signature
from lib.pcb.tests.test_global_projection import design as hierarchy_design
from lib.pcb.tests.test_result_projection import design as results_design
from lib.pcb.tests.test_dipxml_library import source as xml_source


def reopen(document, *, report=None):
    text = dumps(project(document,report=report),preserve=False)
    return assemble_graphics(prepare_core(text)).document


class AscOutputTests(unittest.TestCase):
    def test_xml_standalone_via_uses_the_same_import_normalization_as_other_formats(self):
        root = ElementTree.fromstring(xml_source())
        pattern = root.find('.//Patterns/Pattern')
        pattern.set('Type','Via')
        pattern.find('Pads').remove(pattern.find('Pads/Pad[@Id="41"]'))
        pattern.remove(pattern.find('Shapes'))
        for pair in root.findall('.//InternalConnections'):
            pair.clear()
        component = root.find('Board/Components/Component')
        component.find('Pads').remove(component.find('Pads/Pad[@Id="41"]'))
        document = assemble_graphics(prepare_xml(ElementTree.tostring(root,encoding='unicode'))).document
        component = document.one('/Board/Components/Component')
        self.assertEqual(component.one('Pattern')['Type'],16)
        self.assertEqual((component['RefDes_SilkShow'],component['RefDes_AssyShow']),(2,2))
        rebuilt = reopen(document,report=ConversionReport())
        self.assertEqual(rebuilt.one('/Board/Components/Component')['RefDes_SilkShow'],2)

    def test_empty_removed_pair_table_normalizes_away_and_malformed_data_is_rejected(self):
        data = project(hierarchy_design())
        data.one('/Board').add('RemovedDifferentialPairs')
        document = assemble_graphics(prepare_core(dumps(data,preserve=False))).document
        self.assertIsNone(document.one('/Board').child('RemovedDifferentialPairs'))
        data.one('/Board/RemovedDifferentialPairs').add('RemovedDifferentialPair','Unavailable mapping')
        with self.assertRaises(PcbError):
            assemble_graphics(prepare_core(dumps(data,preserve=False)))

    def test_complete_hierarchy_and_saved_checks_round_trip_without_reference_context(self):
        for make in (hierarchy_design,results_design):
            with self.subTest(design=make.__module__):
                document = make()
                before,expected,report = dumps(document,preserve=False),signature(document.root),ConversionReport()
                with patch.object(Path,'read_bytes',side_effect=AssertionError('companion resource read')):
                    rebuilt = reopen(document,report=report)
                self.assertEqual(signature(rebuilt.root),expected)
                self.assertEqual(signature(reopen(rebuilt).root),expected)
                self.assertEqual(report.notices,[])
                self.assertEqual(dumps(document,preserve=False),before)
                document.references.validate()
                rebuilt.references.validate()

    def test_embedded_definitions_are_composed_with_placed_geometry(self):
        document,report = cache_design(),ConversionReport()
        before = dumps(document,preserve=False)
        rebuilt = reopen(document,report=report)
        self.assertEqual(signature(rebuilt.one('/Board/CacheLib')),signature(document.one('/Board/CacheLib')))
        self.assertEqual(len(rebuilt.select('/Board/Components/Component')),1)
        self.assertEqual(rebuilt.one('/Board/Nets/Net')['Name'],document.one('/Board/Nets/Net')['Name'])
        self.assertIn('pad-persistent-key',{notice.rule for notice in report.warnings})
        self.assertEqual(signature(reopen(rebuilt).root),signature(rebuilt.root))
        self.assertEqual(dumps(document,preserve=False),before)

    def test_current_ratline_pad_assignments_and_edits_share_the_export_indices(self):
        document = hierarchy_design()
        component = document.one('/Board/Components/Component')
        component['RefDes'] = 'U42'
        pads = component.one('Pattern/Pads')
        first,second = pads.children('Pad')
        row = document.one('/Board/Ratlines').add('Ratline')
        row['Enabled'],row['Hidden'] = True,False
        for name,current in dict(X1=1,Y1=2,X2=3,Y2=4).items():
            row[name] = current
        row['Pad1'],row['Pad2'] = first,second
        first.move_to(pads)
        document.one('/Board/Nets/Net')['Name'] = 'Renamed signal'
        projected = project(document,report=ConversionReport())
        self.assertEqual(projected.one('/Board/Connections/Connection').values[5:],(0,0,2,1,'N'))
        rebuilt = reopen(document,report=ConversionReport())
        restored = rebuilt.one('/Board/Ratlines/Ratline')
        self.assertEqual(restored['Pad1']['StringNumber'],'1')
        self.assertEqual(restored['Pad2']['StringNumber'],'2')
        self.assertEqual(rebuilt.one('/Board/Components/Component')['RefDes'],'U42')
        self.assertEqual(rebuilt.one('/Board/Nets/Net')['Name'],'Renamed signal')
        self.assertEqual(signature(rebuilt.root),signature(document.root))

    def test_only_canvas_position_is_rounded_and_scale_keeps_its_percent_unit(self):
        document = hierarchy_design()
        document.root['Xpos'],document.root['Ypos'] = Decimal('.5'),Decimal('-1.5')
        document.root['Scale'] = Decimal('123.4567')
        expected,before,report = signature(document.one('/Board')),dumps(document,preserve=False),ConversionReport()
        projected = project(document,report=report)
        self.assertEqual((projected.one('/Xpos').values,projected.one('/Ypos').values),((0,),(-2,)))
        self.assertEqual(projected.one('/Scale').arguments[0].unit,'%')
        self.assertEqual([notice.rule for notice in report.infos],['viewport-position'])
        rebuilt = reopen(document,report=ConversionReport())
        self.assertEqual(signature(rebuilt.one('/Board')),expected)
        self.assertEqual(rebuilt.root['Scale'],Decimal('123.4567'))
        self.assertEqual(dumps(document,preserve=False),before)

    def test_unmapped_root_or_board_content_cannot_be_silently_omitted(self):
        for path in ('/','/Board'):
            with self.subTest(path=path):
                document = hierarchy_design()
                document.one(path).add('Unmapped',17)
                before = dumps(document,preserve=False)
                with self.assertRaises(PcbError):
                    project(document)
                self.assertEqual(dumps(document,preserve=False),before)


if __name__ == '__main__':
    unittest.main()
