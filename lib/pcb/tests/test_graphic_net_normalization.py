"""Unavailable drawing/pour nets normalize without altering geometry or valid links."""
import unittest

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.pcb.formats.assembly.graphics import assemble_graphics, normalize_graphic_nets
from lib.common.model import Element
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_graphics import design as decoded_design
from lib.pcb.tests.test_asc_graphics import fixture as asc_fixture, design as asc_design
from lib.pcb.tests.test_dipxml_graphics import source as xml_source, design as xml_design


def load(decoded, *, report):
    operation = import_diagnostics('dip')(lambda: assemble_graphics(decoded).document)
    return operation(report=report)


class GraphicNetNormalizationTests(unittest.TestCase):
    def test_unavailable_keys_clear_for_drawings_and_pours(self):
        for key in (999, 100000):
            decoded, _, _ = decoded_design()
            board = decoded.board
            for shape in board.select('Shapes/Shape'):
                shape.one('NetNumber').set_values(key)
            board.one('CopperPours/CopperPour/NetId').set_values(key)
            report = ConversionReport()
            document = load(decoded, report=report)
            shapes = document.select('/Board/Shapes/Shape')
            pour = document.one('/Board/CopperPours/CopperPour')
            self.assertTrue(all(shape['Net'] is None and shape['NetNumber'] == -1 for shape in shapes))
            self.assertIsNone(pour['Net'])
            self.assertEqual(pour.one('Points/pt').values, (3, 4))
            self.assertTrue(pour['Poured'])
            self.assertEqual(pour.one('Fill/Lines/Line')['RegionId'], 7)
            notice, = [notice for notice in report.infos if notice.rule == 'graphic-net-normalization']
            self.assertEqual(len(notice.paths), 3)
            self.assertEqual([notice for notice in report.warnings if notice.rule != 'import-diagnostic'], [])
            self.assertEqual(report.errors, [])
            self.assertTrue(all(shape.child('NetNumber') is None for shape in shapes))
            document.references.validate()

    def test_disabled_targets_are_cleared_by_the_same_import_policy(self):
        decoded, _, _ = decoded_design()
        drawings = decoded.board.select('Shapes/Shape')[:2]
        pours = decoded.board.select('CopperPours/CopperPour')
        disabled = Element('Net')
        disabled.add('Enabled', False)
        changes = normalize_graphic_nets(drawings, pours, {73: disabled})
        self.assertEqual(changes, [*drawings, *pours])
        self.assertTrue(all(shape['NetNumber'] == -1 for shape in drawings))
        self.assertEqual(pours[0]['NetId'], -1)

    def test_no_nets_and_non_copper_layers_have_the_same_general_rule(self):
        decoded, _, _ = decoded_design()
        for net in tuple(decoded.board.select('Nets/Net')):
            net.detach()
        for pad in decoded.board.select('Components/Component/Pattern/Pads/Pad'):
            pad.one('NetNumber').set_values(-1)
        for shape in decoded.board.select('Shapes/Shape'):
            shape.one('Layer').set_values(0)
            shape.one('NetNumber').set_values(0)
        decoded.board.one('CopperPours/CopperPour/NetId').set_values(0)
        document = load(decoded, report=ConversionReport())
        self.assertEqual(document.select('/Board/Nets/Net'), [])
        self.assertTrue(all(shape['Net'] is None for shape in document.select('/Board/Shapes/Shape')))

    def test_valid_non_copper_assignment_is_retained_and_remains_editable(self):
        decoded, _, _ = decoded_design()
        decoded.board.one('Shapes/Shape[1]/Layer').set_values(0)
        report = ConversionReport()
        document = load(decoded, report=report)
        shape = document.one('/Board/Shapes/Shape[1]')
        net = document.one('/Board/Nets/Net')
        self.assertIs(shape['Net'], net)
        net['Name'] = 'Renamed'
        self.assertEqual(shape['Net']['Name'], 'Renamed')
        self.assertNotIn('graphic-net-normalization', [notice.rule for notice in report.infos])
        shape['Net'] = None
        self.assertEqual(shape['NetId'], -1)

    def test_asc_and_xml_enter_the_same_normalization(self):
        source = asc_fixture()
        source.one('/Board/Shapes/Shape/NetNumber').set_values(999)
        source.one('/Board/CopperPours/CopperPour/NetNumber').set_values(999)
        asc = import_diagnostics('asc')(lambda: asc_design(source).document)(report=ConversionReport())
        xml = import_diagnostics('dipxml')(lambda: xml_design(xml_source().replace('NetId="7" Group="90"',
            'NetId="999" Group="90"').replace('Group="90" NetId="7"', 'Group="90" NetId="999"')).document)(
                report=ConversionReport())
        for document in (asc, xml):
            self.assertIsNone(document.one('/Board/Shapes/Shape[1]')['Net'])
            self.assertIsNone(document.one('/Board/CopperPours/CopperPour')['Net'])
            document.references.validate()

    def test_unavailable_layer_and_group_are_not_silently_cleared_by_this_rule(self):
        for field in ('LayId', 'Group'):
            decoded, _, _ = decoded_design()
            decoded.board.one('Shapes/Shape[1]/'+field).set_values(999)
            with self.subTest(field=field), self.assertRaises(PcbError):
                load(decoded, report=ConversionReport())


if __name__ == '__main__':
    unittest.main()
