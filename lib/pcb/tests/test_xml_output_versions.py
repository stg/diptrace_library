"""Older XML output changes syntax conventions without changing the design."""
from decimal import Decimal
import unittest
from xml.etree import ElementTree

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.font_codec import compatibility_size
from lib.common.units import XmlUnits
from lib.pcb.formats import io
from lib.pcb.formats.capabilities import DIPXML, XML_APPLICATION_VERSIONS
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.dipxml.write import project_document
from lib.pcb.formats.dipxml.library_output import project_library
from lib.pcb.formats.dipxml.versions import XmlVersion
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dip_output import configured_document
from lib.pcb.tests.test_dipxml_library import read, source as library_source
from lib.pcb.tests.test_dipxml_pairs import source as pair_source
from lib.pcb.tests.test_xml_document_output import design
from lib.pcb.tests.test_xml_routing_output import with_component_library


PATTERN = '/Board/CacheLib/Slots/Slot/Definition/Pattern'
PART = '/Board/CacheLib/Slots/Slot/Definition/Part'


class XmlOutputVersionTests(unittest.TestCase):
    def test_cached_component_paths_remain_in_every_supported_xml_profile(self):
        document = read(library_source(), report=ConversionReport())
        slot = document.one('/Board/CacheLib/Slots/Slot')
        expected = slot['LibPath'], slot['VariablePath']
        before = model_text(document, preserve=False)
        for version in DIPXML.write_versions:
            with self.subTest(version=version):
                report = ConversionReport()
                output = project_document(document, version=version, report=report)
                path = output.one('/Source/Library/Components/Component/Part/LibPath')
                self.assertEqual((path.one('Path').values[0], path.one('Var').values[0]), expected)
                current = io.parse(dumps(output), report=ConversionReport())
                rebuilt = current.one('/Board/CacheLib/Slots/Slot')
                self.assertEqual((rebuilt['LibPath'], rebuilt['VariablePath']), expected)
                self.assertNotIn('cached-library-path', {n.rule for n in report.warnings})
        self.assertEqual(model_text(document, preserve=False), before)

    def assert_facts(self, current, expected):
        self.assertEqual(current.keys(), expected.keys())
        for path, value in expected.items():
            if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                self.assertLessEqual(abs(current[path]-value), Decimal('1e-23'), path)
            else:
                self.assertEqual(current[path], value, path)

    def test_declared_versions_select_all_three_headers_through_normal_io(self):
        document = configured_document()
        before = model_text(document, preserve=False)
        for version in DIPXML.write_versions:
            with self.subTest(version=version):
                data = io.serialize(document, format='dipxml', version=version, report=ConversionReport())
                root = ElementTree.fromstring(data)
                for header in (root, root.find('Library'), root.find('Library/Library')):
                    self.assertEqual(header.get('Version'), XML_APPLICATION_VERSIONS[version])
                io.parse(data, report=ConversionReport()).references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_panel_metrics_and_cell_spacing_preserve_physical_values_in_all_units(self):
        document = design()
        panel = document.one('/Board/Panel')
        panel['TabWidth'], panel['LeftGap'] = Decimal('1.2345'), Decimal('-0.375')
        document.one('/Board')['RailLeft'] = Decimal('5.25')
        cell = document.one('/Board/Tables/Table/Cells/Cell[1]')
        cell['LineSpacing'], cell['FontWidth'] = Decimal('1.125'), Decimal('.4572')
        expected = signature(panel)
        before = model_text(document, preserve=False)
        for version in (58, 60):
            for units in ('mm', 'mil', 'inch'):
                with self.subTest(version=version, units=units):
                    current = document
                    for _ in range(3):
                        output = project_document(current, version=version, units=units, report=ConversionReport())
                        current = io.parse(dumps(output), report=ConversionReport())
                        self.assert_facts(signature(current.one('/Board/Panel')), expected)
                        self.assertEqual(current.one('/Board')['RailLeft'], Decimal('5.25'))
                        reopened = current.one('/Board/Tables/Table/Cells/Cell[1]')
                        self.assertLessEqual(abs(reopened['LineSpacing']-cell['LineSpacing']), Decimal('1e-23'))
                        self.assertLessEqual(abs(reopened['FontWidth']-cell['FontWidth']), Decimal('1e-23'))
        self.assertEqual(model_text(document, preserve=False), before)

    def test_route_widths_and_signed_phase_lengths_use_distinct_old_domains(self):
        document = read(with_component_library(pair_source()), report=ConversionReport())
        ordinary = document.one('/Board/Nets/Net[1]/Traces/Trace[1]/Points/Point[1]')
        ordinary['PhaseFwd'], ordinary['PhaseBack'] = Decimal('.375'), Decimal('-.625')
        separate_path = '/Board/DifferentialPairs/DifferentialPair/PosSeparateTraces/PosTrace/Points/Point[1]'
        document.one(separate_path)['Width'] = Decimal('.4572')
        for version in (54, 58, 60):
            for units in ('mm', 'mil', 'inch'):
                with self.subTest(version=version, units=units):
                    output = project_document(document, version=version, units=units, report=ConversionReport())
                    current = io.parse(dumps(output), report=ConversionReport())
                    point = current.one('/Board/Nets/Net[1]/Traces/Trace[1]/Points/Point[1]')
                    self.assertEqual((point['PhaseFwd'], point['PhaseBack']), (Decimal('.375'), Decimal('-.625')))
                    self.assertEqual(point['Width'], ordinary['Width'])
                    self.assertEqual(current.one(separate_path)['Width'], Decimal('.4572'))
                    raw = output.one('/Source/Board/DifferentialPairs/DifferentialPair/PosSeparateTraces/PosTrace/Points/Point[1]')
                    self.assertEqual(raw['Width'], Decimal('.4572'))

    def test_equal_geometry_does_not_turn_independent_pad_style_into_inheritance(self):
        document = read(library_source(), report=ConversionReport())
        pad = document.one(PATTERN+'/Pads/Pad[1]')
        pad['Standard'] = False
        before = model_text(document, preserve=False)
        for version in (54, 58, 60):
            output = project_document(document, version=version, report=ConversionReport())
            pattern = output.one('/Source/Library/Library/Patterns/Pattern[1]')
            self.assertNotEqual(pattern.one('DefPad')['Style'], pattern.one('Pads/Pad[1]')['Style'])
            self.assertIsNone(pattern.one('Pads/Pad[1]').child('DefStyle'))
            current = io.parse(dumps(output), report=ConversionReport())
            self.assertFalse(current.one(PATTERN+'/Pads/Pad[1]')['Standard'])
            self.assertEqual(current.one(PATTERN+'/Pads/Pad[1]')['PadWidth_New'], pad['PadWidth_New'])
        self.assertEqual(model_text(document, preserve=False), before)

    def test_independent_geometry_takes_priority_when_old_inheritance_cannot_express_both(self):
        document = read(library_source(), report=ConversionReport())
        pad = document.one(PATTERN+'/Pads/Pad[1]')
        pad['Standard'], pad['PadWidth_New'] = True, Decimal('7.125')
        report = ConversionReport()
        output = project_document(document, version=60, report=report)
        rebuilt = io.parse(dumps(output), report=ConversionReport())
        self.assertEqual(rebuilt.one(PATTERN+'/Pads/Pad[1]')['PadWidth_New'], Decimal('7.125'))
        self.assertFalse(rebuilt.one(PATTERN+'/Pads/Pad[1]')['Standard'])
        self.assertIn('pad-style-inheritance', {n.rule for n in report.warnings})
        self.assertTrue(pad['Standard'])

    def test_library_fonts_round_explicitly_and_keep_stroke_widths(self):
        document = read(library_source(), report=ConversionReport())
        pin = document.one(PART+'/Pins/Pin')
        pin['NameFontSize'], pin['NameFontWidth'], pin['NameFontMono'] = Decimal('6.25'), Decimal('.4572'), True
        shape = document.one(PATTERN+'/Shapes/Shape')
        shape['Type'], shape['FontSize'], shape['FontWidth'], shape['FontMono'] = 7, Decimal('2.5'), Decimal('.375'), True
        before = model_text(document, preserve=False)
        for version in (54, 58, 60):
            for units in ('mm', 'mil', 'inch'):
                report = ConversionReport()
                output = project_document(document, version=version, units=units, report=report)
                current = io.parse(dumps(output), report=ConversionReport())
                reopened = current.one(PART+'/Pins/Pin')
                self.assertEqual(reopened['NameFontSize'], compatibility_size(pin['NameFontSize']))
                self.assertEqual(reopened['NameFontWidth'], pin['NameFontWidth'])
                self.assertFalse(reopened['NameFontMono'])
                reopened = current.one(PATTERN+'/Shapes/Shape')
                self.assertEqual(reopened['FontSize'], compatibility_size(shape['FontSize']))
                self.assertEqual(reopened['FontWidth'], shape['FontWidth'])
                self.assertFalse(reopened['FontMono'])
                self.assertTrue({'fractional-font-size', 'monospaced-font'} <= {n.rule for n in report.warnings})
        self.assertEqual(model_text(document, preserve=False), before)

    def test_older_board_options_warn_without_discarding_library_pad_notes(self):
        document = read(library_source(), report=ConversionReport())
        board = document.one('/Board')
        board['SchemNetClasses'] = True
        document.one('/Board/Nets/Net')['AllowLoops'] = True
        document.one(PATTERN+'/Pads/Pad[1]')['Name'] = 'Authored pad note'
        report = ConversionReport()
        output = project_document(document, version=60, report=report)
        self.assertIsNone(output.one('/Source/Board/Settings').child('SchemNetClasses'))
        self.assertIsNone(output.one('/Source/Board/Nets/Net').child('AllowLoops'))
        current = io.parse(dumps(output), report=ConversionReport())
        self.assertEqual(current.one(PATTERN+'/Pads/Pad[1]')['Name'], 'Authored pad note')
        self.assertTrue({'net-loop-policy', 'schematic-net-classes'} <= {n.rule for n in report.warnings})
        self.assertNotIn('cached-library-path', {n.rule for n in report.warnings})
        self.assertTrue(board['SchemNetClasses'])
        self.assertTrue(document.one('/Board/Nets/Net')['AllowLoops'])

    def test_oldest_profile_omits_only_its_unavailable_board_fields(self):
        document = read(library_source(), report=ConversionReport())
        board = document.one('/Board')
        component = board.one('Components/Component')
        pad = component.one('Pattern/Pads/Pad[1]')
        net = board.one('Nets/Net')
        board['ShieldGroup'], component['ShieldGroup'], pad['ShieldGroup'] = 3, 4, 5
        net['HiddenId'] = 12345
        panel = board.add('Panel')
        panel['LeftGap'] = Decimal('3.125')
        board['PanelDX'], board['RailLeft'] = Decimal('7.125'), Decimal('4.375')
        cached = document.one(PATTERN+'/Pads/Pad[1]')
        cached['Name'] = 'Keep this library note'
        before, report = model_text(document, preserve=False), ConversionReport()
        output = io.project(document, format='dipxml', version=54, report=report)
        target = output.one('/Source/Board')
        self.assertFalse(any(node.child('ShieldGroup') is not None for node in target.walk(include_self=True)))
        self.assertIsNone(target.one('Nets/Net').child('HiddenId'))
        self.assertIsNone(target.one('Panel').child('LeftGap'))
        self.assertEqual(target.one('Panel')['RailLeft'], Decimal('4.375'))
        self.assertEqual(target.one('Panel')['ColumnSpacing'], Decimal('2.375'))
        rebuilt = io.parse(dumps(output), report=ConversionReport())
        self.assertEqual(rebuilt.one(PATTERN+'/Pads/Pad[1]')['Name'], 'Keep this library note')
        self.assertEqual(rebuilt.one('/Board')['PanelDX'], Decimal('7.125'))
        self.assertTrue({'shield-groups', 'persistent-net-id', 'panel-side-gaps'} <= {n.rule for n in report.warnings})
        self.assertEqual(model_text(document, preserve=False), before)

    def test_oldest_pattern_drawing_pad_association_warns_and_preserves_geometry(self):
        document = read(library_source(), report=ConversionReport())
        shape = document.one(PATTERN+'/Shapes/Shape')
        shape['Pad'] = shape.parent.parent.one('Pads/Pad[1]')
        before = model_text(document, preserve=False)
        for version in (54, 58):
            report = ConversionReport()
            output = project_document(document, version=version, report=report)
            style = output.one('/Source/Library/Components/Component/Part/Pattern')['Style']
            drawing = output.one('/Source/Library/Library/Patterns/Pattern',
                                  where=lambda row: row['PatternStyle'] == style).one('Shapes/Shape')
            self.assertEqual(drawing.get('PadId'), None if version == 54 else 17)
            self.assertEqual('pattern-drawing-pad' in {n.rule for n in report.warnings}, version == 54)
            rebuilt = io.parse(dumps(output), report=ConversionReport())
            self.assertEqual(signature(rebuilt.one(PATTERN+'/Shapes/Shape/Points_New')),
                             signature(shape.one('Points_New')))
        self.assertEqual(model_text(document, preserve=False), before)

    def test_oldest_panel_gap_omission_compares_with_the_spacing_fallback_including_zero(self):
        document = configured_document()
        board, panel = document.one('/Board'), document.one('/Board/Panel')
        board['PanelDX'], board['PanelDY'] = 6, 9
        for name, value in (('LeftGap', 6), ('RightGap', 6), ('TopGap', 9), ('BottomGap', 9)):
            panel[name] = value
        for left, warned in ((6, False), (0, True)):
            with self.subTest(left=left):
                panel['LeftGap'] = left
                report = ConversionReport()
                output = project_document(document, version=54, units='inch', report=report)
                self.assertIsNone(output.one('/Source/Board/Panel').child('LeftGap'))
                self.assertEqual('panel-side-gaps' in {notice.rule for notice in report.warnings}, warned)
                self.assertEqual(panel['LeftGap'], left)

    def test_embedded_library_projection_honors_its_profile_without_a_board_wrapper(self):
        document = read(library_source(), report=ConversionReport())
        pin = document.one(PART+'/Pins/Pin')
        pin['NameFontSize'], pin['NameFontWidth'], pin['NameFontMono'] = Decimal('6.25'), Decimal('.4572'), True
        before = model_text(document, preserve=False)
        for version in (54, 58, 60):
            result = project_library(document.one('/Board'), units=XmlUnits('mil'),
                                     profile=XmlVersion.output(version), report=ConversionReport()).element
            self.assertEqual(result['Version'], XML_APPLICATION_VERSIONS[version])
            self.assertEqual(result.one('Library')['Version'], XML_APPLICATION_VERSIONS[version])
            self.assertFalse(any(node.child(name) is not None for node in result.walk(include_self=True)
                                 for name in ('FontSizeFloat', 'FontMono', 'DefStyle')))
            self.assertEqual(result.one('Components/Component/Part/Pins/Pin/NameFont')['Width'], Decimal('.4572'))
        self.assertEqual(model_text(document, preserve=False), before)
