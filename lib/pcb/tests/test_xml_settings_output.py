"""Document preferences project from current data, independent of input version."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.units import XmlUnits
from lib.common.xml_library_output import project_project_libraries
from lib.pcb.formats.dipxml.settings_output import (project_settings, project_sheet, project_panel,
                                                  project_connectivity)
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_settings import source
from lib.pcb.tests.test_dipxml_library import read
from lib.pcb.tests.test_xml_routing_output import context, with_component_library
from lib.pcb.tests.test_title_relations import source as title_source


def reopen(document, *, units='mm', report=None):
    output, _ = context(document, units=units, report=report)
    board, target, scale = document.one('/Board'), output.one('/Source/Board'), XmlUnits(units)
    for section in (project_settings(board, units=scale, report=report), project_sheet(board, units=scale),
                    project_panel(board, units=scale), project_connectivity(board), project_project_libraries(board)):
        if section.children():
            target.append(section)
    return read(dumps(output), report=ConversionReport()), output


class XmlSettingsOutputTests(unittest.TestCase):
    def assert_facts(self, actual, expected):
        self.assertEqual(actual.keys(), expected.keys())
        for name, value in expected.items():
            if isinstance(value, tuple):
                self.assert_facts(dict(enumerate(actual[name])), dict(enumerate(value)))
            elif isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                self.assertLessEqual(abs(actual[name]-value), Decimal('1e-23'), name)
            else:
                self.assertEqual(actual[name], value, name)

    def test_current_preferences_sheet_panel_and_markings_survive_units_and_repeated_output(self):
        document = read(with_component_library(source()), report=ConversionReport())
        before = model_text(document, preserve=False)
        branches = ('Settings', 'SheetSettings', 'Panel', 'ConnectivityCheck', 'Userfields_Global')
        expected = {name: signature(document.one('/Board/'+name)) for name in branches}
        own = document.one('/Board')
        scalars = {name: own[name] for name in (
            'CompRotate', 'PatternFontVector', 'CompFontName', 'CompFontSize', 'PatternFontWidth',
            'PatternFontScale', 'OriginX', 'OriginY', 'RelSchem', 'RelSchem_Variable', 'Toplock', 'Bottomlock',
            'LockNetStructure', 'PanelX', 'PanelY', 'PanelDX', 'PanelDY', 'RailShow', 'RailLeft', 'RailRight',
            'RailTop', 'RailBottom', 'ProjectDir', 'RefDes_Global_SilkShow', 'RefDes_Global_AssyAlign')}
        for units in ('mm', 'mil', 'inch'):
            current = document
            for _ in range(3):
                current, _ = reopen(current, units=units)
                for name in branches:
                    self.assert_facts(signature(current.one('/Board/'+name)), expected[name])
                self.assert_facts({name: current.one('/Board')[name] for name in scalars}, scalars)
                self.assert_facts({name: current.root[name] for name in ('Scale', 'Xpos', 'Ypos')},
                                  {name: document.root[name] for name in ('Scale', 'Xpos', 'Ypos')})
                current.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_old_panel_input_modernizes_once_and_remains_stable_in_current_output(self):
        for version in ('4.3.0.3', '4.3.0.4', '5.3.4.9'):
            with self.subTest(version=version):
                document = read(with_component_library(source(version)), report=ConversionReport())
                expected = signature(document.one('/Board/Panel'))
                current = document
                for _ in range(3):
                    current, _ = reopen(current, units='mil')
                    self.assert_facts(signature(current.one('/Board/Panel')), expected)
                    self.assertEqual(current.one('/Board')['PanelDY'], document.one('/Board')['PanelDY'])

    def test_shared_sheet_titles_follow_field_reordering_and_keep_styles(self):
        document = read(with_component_library(title_source()), report=ConversionReport())
        block = document.one('/Board/SheetSettings/TitleBlocks/TitleBlock[1]')
        first, second = block.select('Contents/Content')
        second.move_to(second.parent, 0)
        expected = signature(block)
        before = model_text(document, preserve=False)
        current = document
        for _ in range(3):
            current, _ = reopen(current, units='inch')
            block = current.one('/Board/SheetSettings/TitleBlocks/TitleBlock[1]')
            self.assert_facts(signature(block), expected)
            self.assertIs(block.one('Cells/Cell[1]')['Field'], block.one('Contents/Content[2]'))
            current.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_routing_views_follow_class_edits_and_known_omissions_warn(self):
        document = read(with_component_library(source()), report=ConversionReport())
        routing = document.one('/Board/Settings/Routing')
        routing['TraceWidth'], routing['TraceClearance'] = Decimal('1.75'), Decimal('.875')
        routing['PadClearance'], routing['ViaApply'] = 2, 1
        document.one('/Board/Userfields_Global/UserField')['Name'] = 'Order code'
        before, report = model_text(document, preserve=False), ConversionReport()
        current, _ = reopen(document, report=report)
        self.assertEqual(current.one('/Board/Settings/Routing')['TraceWidth'], Decimal('1.75'))
        self.assertEqual(current.one('/Board/Settings/Routing')['TraceClearance'], Decimal('.875'))
        self.assertIn('routing-default-options', {item.rule for item in report.warnings})
        self.assertNotIn('global-userfield-value', {item.rule for item in report.warnings})
        self.assertEqual(current.one('/Board/Userfields_Global/UserField')['Value'], 'ordercode')
        self.assertEqual(model_text(document, preserve=False), before)

    def test_negative_zone_strokes_and_literal_search_paths_need_no_external_files(self):
        paths = '''<ProjectLibs Sorted="Y"><Folders><Folder><Path>parts</Path><Var>${PARTS}</Var>
          </Folder></Folders><Libs><Lib><Path>parts.lib</Path><Var>${PARTS}/parts.lib</Var></Lib></Libs></ProjectLibs>'''
        text = source().replace('<Board>', '<Board>'+paths, 1).replace(
            '<FontLineWidth>0.2</FontLineWidth>', '<FontLineWidth>-2</FontLineWidth>')
        document = read(with_component_library(text), report=ConversionReport())
        with patch('pathlib.Path.open', side_effect=AssertionError('external file access')):
            current, _ = reopen(document, units='inch')
        self.assertEqual(current.one('/Board/SheetSettings/BorderZones')['FontLineWidth'], -2)
        for name in ('ProjectLibs_Folders', 'ProjectLibs_Libs'):
            self.assertEqual(signature(current.one('/Board/'+name)), signature(document.one('/Board/'+name)))
        self.assertTrue(current.one('/Board')['ProjectLibs_Sorted'])

    def test_unknown_preferences_fail_without_mutating_current_data(self):
        document = read(with_component_library(source()), report=ConversionReport())
        document.one('/Board/Settings').add('UnmappedChoice', 3)
        before = model_text(document, preserve=False)
        with self.assertRaises(PcbError):
            reopen(document)
        self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
