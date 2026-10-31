"""PCB XML preferences resolve into the existing editable settings records."""
from decimal import Decimal
import unittest

from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.formats.dipxml.versions import XmlVersion
from lib.pcb.tests.test_dipxml_classes import source as class_source
from lib.pcb.tests.test_dipxml_electrical import prepared


SETTINGS = '''<SheetSettings><Scale>150</Scale><Xpos>1.2</Xpos><Ypos>-2.3</Ypos>
  <SheetWidth>100</SheetWidth><SheetHeight>80</SheetHeight><LeftMargin>5</LeftMargin>
  <DisplayTitles>Y</DisplayTitles><DisplaySheet>N</DisplaySheet>
  <BorderZones><Visible>Y</Visible><FontName>Vector</FontName><FontSize>10</FontSize>
    <FontLineWidth>0.2</FontLineWidth><HorzZones>4</HorzZones><VertZones>3</VertZones>
    <HorzBorderSize>2</HorzBorderSize><Border>N</Border></BorderZones></SheetSettings>
<Settings><Markings><CompRotate>Y</CompRotate><FontVector>N</FontVector><FontName>Sans</FontName>
  <FontSize>5</FontSize><FontSizeFloat>5.5</FontSizeFloat><FontWidth>0.25</FontWidth><FontScale>1.2</FontScale>
  <RefDesGlobal SilkShow="Show" SilkAlign="Auto" AssyShow="Hide" AssyAlign="Center"/>
  <AddFieldsGlobal><AddField SilkShow="Show" SilkAlign="Top" AssyShow="Hide" AssyAlign="Auto">
    <Name>Order code</Name></AddField></AddFieldsGlobal></Markings>
  <Grid><Visible>Y</Visible><Snap>N</Snap><Size>0.1</Size><YSize>0.2</YSize><YIdentical>N</YIdentical></Grid>
  <Origin><Visible>Y</Visible><AxisColor>123</AxisColor><X>2</X><Y>3</Y></Origin>
  <Assembly><Pads>Y</Pads><Silk>N</Silk><CompBorders>Y</CompBorders><BoardOutline>N</BoardOutline></Assembly>
  <LineWidth><Silk>0.25</Silk><Table>0.3</Table><CompOutline>0.05</CompOutline></LineWidth>
  <Routing><Router>Grid</Router><TraceWidth>0.4</TraceWidth><TraceClearance>0.3</TraceClearance>
    <BoardClearance>0.2</BoardClearance><ViaSize>0.6</ViaSize><ViaHole>0.3</ViaHole><FanoutLength>1</FanoutLength></Routing>
  <LayerDisplayMode>Contrast</LayerDisplayMode><JumperLayer>Signal</JumperLayer>
  <EditInactiveLayer>Y</EditInactiveLayer><StackLength>Y</StackLength><SignalDelayLength>N</SignalDelayLength>
  <SolderMaskSwell>0.1</SolderMaskSwell><PasteMaskShrink>0.05</PasteMaskShrink>
  <LayerPanel TopAssy="Y" BotAssy="N"/><RelatedSchem><Path>design.dch</Path><Var>${ROOT}/design.dch</Var></RelatedSchem>
  <TopComponentLock>Y</TopComponentLock><BottomComponentLock>N</BottomComponentLock>
  <LockNetStructure>Y</LockNetStructure><FlipTextAuto>N</FlipTextAuto><ProjectDir>project</ProjectDir>
</Settings><ConnectivityCheck Traces="Y" Shapes="N" CopperPours="Y"/>'''
PANEL = '''<Panel Type="Tab Routing" Columns="2" Rows="3" ColumnSpacing="4" RowSpacing="5"
  PanelizeSingle="Y" RailShow="Y" RailLeft="1" RailRight="2" RailTop="3" RailBottom="4"
  TabWidth="2" TabRadius="1" TabStep="10" HoleDiam="0.5" HoleStep="1.2" HoleInset="0.1"
  HoleKeepout="0.2" TabsDone="Y" CombinedRadius="0.4" KeepMaterial="N" BorderTabs="2" LeftGap="3">
  <HorzTabsX><Item>1</Item></HorzTabsX><VertTabsY><Item>2</Item></VertTabsY></Panel>'''


def source(version='5.3.5.1'):
    return class_source().replace('Version="5.3"', f'Version="{version}"').replace(
        '<Board>', '<Board>'+SETTINGS+PANEL, 1)


class PcbXmlSettingsTests(unittest.TestCase):
    def test_named_fields_units_and_global_markings_enter_current_records(self):
        result = assemble_rules(prepared(source()))
        doc, board = result.document, result.document.one('/Board')
        settings, sheet = board.one('Settings'), board.one('SheetSettings')
        self.assertEqual((doc.root['Scale'], doc.root['Xpos'], doc.root['Ypos']),
                         (150, Decimal('3.6'), Decimal('6.9')))
        self.assertEqual((sheet['SheetWidth'], sheet['SheetHeight'], sheet['LeftMargin']), (300, 240, 15))
        self.assertEqual(sheet.one('BorderZones')['FontLineWidth'], Decimal('.6'))
        self.assertTrue(sheet['DisplayTitles'])
        self.assertFalse(sheet['DisplaySheet'])
        self.assertEqual((board['CompFontSize'], board['PatternFontWidth']), (Decimal('5.5'), Decimal('.25')))
        self.assertEqual((board['OriginX'], board['OriginY']), (6, -9))
        self.assertEqual((board['RefDes_Global_SilkShow'], board['RefDes_Global_AssyAlign']), (1, 1))
        field = board.one('Userfields_Global/UserField')
        self.assertEqual((field['Name'], field['Value'], field['SilkAlign']), ('Order code', 'ordercode', 2))
        self.assertIsNone(field.child('Value'))
        self.assertEqual((settings['GridSize'], settings['YGridSize']), (Decimal('.3'), Decimal('.6')))
        self.assertEqual(settings['SilkLineWidth'], Decimal('.75'))
        self.assertEqual((settings['LayerDisplayMode'], settings['JumperLayer']), (2, 2))
        self.assertEqual(settings.one('Routing')['Router'], 1)
        self.assertTrue(settings.one('LayerPanel')['TopAssy'])
        self.assertEqual((board['RelSchem'], board['RelSchem_Variable']), ('design.dch', '${ROOT}/design.dch'))
        self.assertFalse(board.one('ConnectivityCheck')['Shapes'])

    def test_routing_defaults_share_the_default_class_values_and_edit_path(self):
        result = assemble_rules(prepared(source()))
        routing = result.document.one('/Board/Settings/Routing')
        row = result.classes[0].one('LayProperties/LayProperty')
        self.assertEqual((routing['TraceWidth'], row['Width']), (Decimal('1.2'), Decimal('1.2')))
        self.assertIsNone(routing.child('TraceWidth'))
        routing['TraceWidth'] = 2
        self.assertEqual(row['Width'], 2)
        row['Clearance'] = Decimal('.9')
        self.assertEqual(routing['TraceClearance'], Decimal('.9'))

    def test_panel_metrics_follow_the_xml_compatibility_boundary(self):
        for version, metric, spacing, x, y in (
                ('4.3.0.3', 2, -15, 1, 2),
                ('4.3.0.4', 2, 15, 3, -6),
                ('5.3.4.9', 2, 15, 3, -6),
                ('5.3.5.0', 6, 15, 3, -6)):
            with self.subTest(version=version):
                board = assemble_rules(prepared(source(version))).document.one('/Board')
                panel = board.one('Panel')
                self.assertEqual(panel['TabWidth'], metric)
                self.assertEqual((board['PanelX'], board['PanelY'], board['PanelDX'], board['PanelDY']), (2, 3, 12, spacing))
                self.assertEqual(panel.one('HorzTabsX/Item')['Position'], x)
                self.assertEqual(panel.one('VertTabsY/Item')['Position'], y)
                panel.one('HorzTabsX/Item')['Position'] = 42
                self.assertEqual(panel.one('HorzTabsX/Item')['Position'], 42)

    def test_context_free_negative_font_strokes_and_unavailable_options_stay_distinct(self):
        doc = assemble_rules(prepared(source().replace('<FontLineWidth>0.2</FontLineWidth>',
                                                       '<FontLineWidth>-2</FontLineWidth>'))).document
        self.assertEqual(doc.one('/Board/SheetSettings/BorderZones')['FontLineWidth'], -2)
        self.assertIsNone(doc.one('/Board/Settings/LayerPanel').child('Board'))
        self.assertIsNone(doc.one('/Board/Settings/Routing').child('PadClearance'))
        copied = doc.clone()
        copied.one('/Board/Userfields_Global/UserField')['Name'] = 'Changed'
        self.assertEqual(doc.one('/Board/Userfields_Global/UserField')['Name'], 'Order code')

    def test_missing_application_version_uses_current_panel_conventions(self):
        text = source().replace('Version="5.3.5.1"', '')
        board = assemble_rules(prepared(text)).document.one('/Board')
        self.assertEqual(board.one('Panel')['TabWidth'], 6)
        self.assertEqual(board['PanelDY'], 15)

    def test_library_search_paths_are_shared_literal_metadata_without_discovery(self):
        paths = '''<ProjectLibs Sorted="Y"><Folders><Folder><Path>parts</Path>
          <Var>${PARTS}</Var></Folder></Folders><Libs><Lib><Path>parts.lib</Path>
          <Var>${PARTS}/parts.lib</Var></Lib></Libs></ProjectLibs>'''
        doc = assemble_rules(prepared(source().replace('<Board>', '<Board>'+paths, 1))).document
        folder = doc.one('/Board/ProjectLibs_Folders/Folder')
        library = doc.one('/Board/ProjectLibs_Libs/Lib')
        self.assertTrue(doc.one('/Board')['ProjectLibs_Sorted'])
        self.assertEqual((folder['Path'], folder['VariablePath']), ('parts', '${PARTS}'))
        self.assertEqual((library['Path'], library['VariablePath']), ('parts.lib', '${PARTS}/parts.lib'))
        self.assertEqual(folder.schema.name, library.schema.name)
        library['Path'] = 'changed.lib'
        self.assertEqual(library['VariablePath'], '${PARTS}/parts.lib')

    def test_unknown_preferences_and_invalid_version_are_explicit_limits(self):
        for before, after in (('<Snap>N</Snap>', '<Snap>Yes</Snap>'),
                              ('<ProjectDir>project</ProjectDir>', '<Unknown>1</Unknown>'),
                              ('<Router>Grid</Router>', '<Router>Unknown</Router>')):
            with self.subTest(after=after), self.assertRaises(ValueError):
                prepared(source().replace(before, after))
        with self.assertRaisesRegex(ValueError, 'application version'):
            XmlVersion.parse('5.3 beta')
        self.assertEqual(XmlVersion.parse('5.3').application, (5, 3, 0, 0))


if __name__ == '__main__':
    unittest.main()
