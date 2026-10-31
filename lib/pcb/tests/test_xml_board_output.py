"""Board XML geometry and dimensions retain current identities and authored data."""
from decimal import Decimal
from unittest.mock import patch
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.units import XmlUnits
from lib.pcb.formats.dipxml.dimension_output import project_dimensions
from lib.pcb.formats.dipxml.graphic_output import (project_outline, project_non_signals,
                                                project_layer_panel, project_drawings)
from lib.pcb.formats.dipxml.output_keys import OutputKeys
from lib.pcb.formats.dipxml.pour_output import project_pours
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_dimensions import text as dimension_source, target
from lib.pcb.tests.test_dipxml_library import read
from lib.pcb.tests.test_non_signal_layers import source as non_signal_source
from lib.pcb.tests.test_xml_routing_output import context, with_component_library


def design():
    return read(with_component_library(dimension_source()), report=ConversionReport())


def reopen(document, *, units='mm', report=None, legacy_picture_files=None):
    report = ConversionReport() if report is None else report
    output, library = context(document, units=units, report=report)
    board, result = document.one('/Board'), output.one('/Source/Board')
    scale, keys = XmlUnits(units), OutputKeys(board, library)
    result.append(project_outline(board, units=scale))
    result.append(project_non_signals(board))
    panel = project_layer_panel(board)
    if panel.children():
        result.add('Settings').append(panel)
    result.append(project_drawings(board, units=scale, report=report, legacy_picture_files=legacy_picture_files))
    result.append(project_pours(board, units=scale, report=report))
    result.append(project_dimensions(board, keys=keys, units=scale, report=report))
    return read(dumps(output), report=ConversionReport()), output


class XmlBoardOutputTests(unittest.TestCase):
    def assert_facts(self, actual, expected):
        self.assertEqual(actual.keys(), expected.keys())
        for name, value in expected.items():
            if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                self.assertLessEqual(abs(actual[name]-value), Decimal('1e-23'), name)
            else:
                self.assertEqual(actual[name], value, name)

    def test_authored_geometry_dimensions_and_picture_vectors_survive_units_and_repeated_output(self):
        document = design()
        before = model_text(document, preserve=False)
        paths = ('/Board/Points', '/Board/Shapes', '/Board/Dimensions', '/Board/CopperPours')
        expected = {path: signature(document.one(path)) for path in paths}
        for units in ('mm', 'mil', 'inch'):
            with self.subTest(units=units):
                current = document
                for _ in range(3):
                    current, output = reopen(current, units=units)
                    xml = ElementTree.fromstring(dumps(output))
                    for dimension in xml.findall('./Board/Dimensions/Dimension'):
                        self.assertNotIn('FontName', dimension.attrib)
                        self.assertIsNotNone(dimension.find('FontName'))
                    for path in paths:
                        self.assert_facts(signature(current.one(path)), expected[path])
                    for name in ('Enabled', 'Selected', 'Locked', 'PanelExclude', 'ShieldGroup'):
                        self.assertEqual(current.one('/Board')[name], document.one('/Board')[name])
                    current.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_reordered_outline_pad_trace_and_drawing_targets_keep_their_identity(self):
        document = design()
        dimension = document.one('/Board/Dimensions/Dimension[1]')
        point = target(document, dimension)
        point.move_to(point.parent, 0)
        pad = document.one('/Board/Components/Component/Pattern/Pads/Pad[1]')
        pad.move_to(pad.parent, 1)
        trace = document.one('/Board/Nets/Net/Traces/Trace[1]')
        trace.move_to(trace.parent, 1)
        shape = document.one('/Board/Shapes/Shape[1]')
        shape.move_to(shape.parent, 1)
        expected = signature(document.one('/Board/Dimensions'))
        rebuilt, _ = reopen(document)
        self.assert_facts(signature(rebuilt.one('/Board/Dimensions')), expected)
        dimensions = rebuilt.select('/Board/Dimensions/Dimension')
        self.assertIs(target(rebuilt, dimensions[0]), rebuilt.one('/Board/Points/pt[1]'))
        self.assertIs(target(rebuilt, dimensions[1]), rebuilt.one('/Board/Components/Component/Pattern/Pads/Pad[2]'))
        self.assertIs(target(rebuilt, dimensions[1], 1), rebuilt.one('/Board/Nets/Net/Traces/Trace[2]/Points/Point[2]'))
        self.assertIs(target(rebuilt, dimensions[2]), rebuilt.one('/Board/Shapes/Shape[2]'))
        rebuilt.references.validate()

    def test_custom_layers_visibility_and_remembered_dimension_choice_follow_reordering(self):
        document = read(non_signal_source(), report=ConversionReport())
        before = model_text(document, preserve=False)
        _, output = reopen(document)
        outline = ElementTree.fromstring(dumps(output)).find('./Board/BoardOutline')
        self.assertNotIn('Locked', outline.attrib)
        self.assertEqual(model_text(document, preserve=False), before)
        first, second = document.select('/Board/NonSignals/NonSignal')
        second.move_to(second.parent, 0)
        first['Name'] = 'Assembly notes'
        expected = signature(document.one('/Board/NonSignals'))
        rebuilt, _ = reopen(document)
        self.assert_facts(signature(rebuilt.one('/Board/NonSignals')), expected)
        dimension = rebuilt.one('/Board/Dimensions/Dimension')
        self.assertIs(dimension['NonSignalLayer'], rebuilt.one('/Board/NonSignals/NonSignal[1]'))
        self.assertEqual([layer['Visible'] for layer in rebuilt.select('/Board/NonSignals/NonSignal')], [False, True])

    def test_picture_sources_are_resolved_only_by_explicit_paths_or_a_supplied_table(self):
        document = design()
        picture = document.one('/Board/Shapes/Shape[2]')
        picture['Picture_File'], picture['Picture_File_Variable'] = '', ''
        picture['BitmapIndex'] = 2
        before, report = model_text(document, preserve=False), ConversionReport()
        with patch('pathlib.Path.open', side_effect=AssertionError('external picture access')):
            rebuilt, _ = reopen(document, report=report)
        self.assertEqual(rebuilt.one('/Board/Shapes/Shape[2]')['BitmapIndex'], -1)
        self.assertIn('unresolved-picture-reference', {notice.rule for notice in report.warnings})
        report = ConversionReport()
        rebuilt, _ = reopen(document, report=report, legacy_picture_files=('', '', 'pictures/logo.png'))
        self.assertEqual(rebuilt.one('/Board/Shapes/Shape[2]')['Picture_File'], 'pictures/logo.png')
        self.assertNotIn('unresolved-picture-reference', {notice.rule for notice in report.warnings})
        self.assertEqual(model_text(document, preserve=False), before)

    def test_unmapped_and_invalid_geometry_is_rejected_without_modifying_the_source(self):
        for invalid in ('unknown', 'layer'):
            with self.subTest(invalid=invalid):
                document = design()
                shape = document.one('/Board/Shapes/Shape[1]')
                if invalid == 'unknown':
                    shape.add('UnmappedDrawingData', 3)
                else:
                    shape['LayerTarget'] = None
                before = model_text(document, preserve=False)
                with self.assertRaises(PcbError):
                    reopen(document)
                self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
