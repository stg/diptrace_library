"""PCB XML tables import into the same editable grids and row relationships."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.cell_records import CELL
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import Property, ReferenceError
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.tests.test_dipxml_electrical import prepared, NETS
from lib.pcb.tests.test_dipxml_components import SOURCE


TABLES = '''<Tables><Table Id="93" Layer="Top Silk" Orientation="270" X1="1" Y1="2" X2="3" Y2="4"
    CellWidth="5" CellHeight="6" TextAlign="Center" FontVector="Y" FontMono="Y"
    FontSize="3" FontSizeFloat="3.25" FontWidth="0.2" FontScale="1.1" LineSpacing="1.3">
  <Name>Parts</Name><FontName>Arial</FontName>
  <AutoUpdate Type="BOM" Units="mm" RowType="Name and Value" AssemblyVariant="0" Header="Y"
      BomRowNumber="Y" BomTotal="N" PickOffX="2" PickOffY="3" PickMirror="Y" PickOrigin="N">
    <AssemblyName>Production</AssemblyName><Separator>.</Separator><Supplier>Vendor Y</Supplier>
    <Columns><Column Type="2" TextAlign="Right" Width="5"><Name>Value</Name><Title>Rating</Title></Column></Columns>
  </AutoUpdate>
  <RowComponents><RowCom><Item>0</Item></RowCom><RowCom><Item>-1</Item></RowCom></RowComponents>
  <ColWidths><Item>1</Item><Item>2</Item></ColWidths><RowHeights><Item>3</Item></RowHeights>
  <Cells><Cell><Cell X1="1" Y1="2" X2="2" Y2="3" FontVector="Y" FontMono="Y" FontSize="2"
      FontSizeFloat="2.5" FontWidth="0.1" FontScale="1" LineSpacing="1.2" TextAlign="Right">
    <FontName>Tahoma</FontName><TextLines><TextLine>first</TextLine><TextLine></TextLine>
      <TextLine>last</TextLine><TextLine>   </TextLine></TextLines></Cell></Cell>
    <Cell><Cell X1="2" Y1="2" X2="4" Y2="3"/></Cell></Cells>
</Table></Tables>'''


def source(tables=TABLES, *, version='5.3.5.1'):
    return SOURCE.replace('Version="5.3"', f'Version="{version}"', 1).replace('</Board>', NETS+tables+'</Board>')


@import_diagnostics('dipxml')
def read(text):
    return assemble_graphics(prepared(text)).document


class PcbXmlTableTests(unittest.TestCase):
    def test_shared_cells_keep_text_geometry_style_and_grid_order(self):
        document = read(source(), report=ConversionReport())
        table = document.one('/Board/Tables/Table')
        cell, empty = table.select('Cells/Cell')
        self.assertIs(cell.schema, CELL)
        self.assertEqual((table['Id'], table['Orientation'], table['Layer']), (0, 3, 1))
        self.assertEqual((table['X1'], table['Y1'], table['X2'], table['Y2']), (3, -6, 9, -12))
        self.assertEqual((table['DefCellWidth'], table['DefCellHeight']), (15, 18))
        self.assertEqual((table['DefFontSize'], table['DefFontWidth'], table['DefFontMono']),
                         (Decimal('3.25'), Decimal('.6'), True))
        self.assertEqual(cell['Text'], 'first\n\nlast')
        self.assertIsNone(cell.child('TextLines'))
        self.assertEqual((cell['FontSize'], cell['FontWidth'], cell['FontMono']),
                         (Decimal('2.5'), Decimal('.3'), True))
        self.assertEqual((cell['Column'], cell['Row'], empty['Column'], empty['Row']), (0, 0, 1, 0))
        self.assertEqual(empty['Text'], '')
        self.assertEqual((empty['FontSize'], empty['FontScale'], empty['FontWidth'], empty['VectorFont']), (0, 0, 0, False))
        self.assertEqual(cell.values, (3, -6, 6, -9))
        document.references.validate()

    def test_documentation_settings_and_row_positions_are_not_xml_component_ids(self):
        document = read(source(), report=ConversionReport())
        table = document.one('/Board/Tables/Table')
        update = table.one('AutoUpdate')
        self.assertEqual((table['DocType'], table['DocUnits'], update['RowType']), (2, 3, 2))
        self.assertEqual(table['Supplier'], 'Vendor Y')
        self.assertEqual((update['PickOffX'], update['PickOffY']), (6, 9))
        column = update.one('Columns/Column')
        self.assertEqual((column['Width'], column['Name'], column['Title']), (15, 'Value', 'Rating'))
        member = table.one('RowComponents/Row[1]/Item')
        component = document.one('/Board/Components/Component')
        self.assertIs(member['Component'], component)
        self.assertEqual(member['ComponentIndex'], 0)
        self.assertIsNone(table.one('RowComponents/Row[2]/Item')['Component'])
        self.assertIsNone(member.child('UnresolvedComponentIndex'))
        observer = document.root.add('MemberPosition', -1)
        document.references.bind(observer, member, Property(observer, 'ComponentIndex'))
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            document.copy(component, parent=component.parent, index=0, fields={'RefDes': 'U2'})
            self.assertEqual(observer.values, (1,))
            table.one('Cells/Cell[1]')['Text'] = 'Edited'
            self.assertEqual(column['Title'], 'Rating')
        clone = document.clone()
        self.assertIsNot(clone.one('/Board/Tables/Table/RowComponents/Row[1]/Item')['Component'], component)
        document.references.validate()
        clone.references.validate()

    def test_old_pickoff_y_and_font_strokes_modernize_at_their_own_version_gates(self):
        old = read(source(version='4.3.0.3'), report=ConversionReport()).one('/Board/Tables/Table')
        modern = read(source(version='4.3.0.5'), report=ConversionReport()).one('/Board/Tables/Table')
        self.assertEqual((old.one('AutoUpdate')['PickOffY'], modern.one('AutoUpdate')['PickOffY']), (-9, 9))
        self.assertEqual((old['DefFontWidth'], modern['DefFontWidth']), (Decimal('.2'), Decimal('.2')))
        self.assertEqual(modern.one('Cells/Cell[1]')['FontWidth'], Decimal('.1'))
        self.assertEqual(modern.one('Cells/Cell[1]')['LineSpacing'], Decimal('3.6'))
        current = read(source(), report=ConversionReport()).one('/Board/Tables/Table')
        self.assertEqual(current.one('Cells/Cell[1]')['LineSpacing'], Decimal('1.2'))
        text = TABLES.replace('Type="BOM"', 'Type="Pick and Place"').replace('RowType="Name and Value"', 'RowType="Bottom"')
        table = read(source(text), report=ConversionReport()).one('/Board/Tables/Table')
        self.assertEqual((table['DocType'], table.one('AutoUpdate')['RowType']), (3, 2))

    def test_unavailable_component_position_warns_and_can_be_repaired(self):
        report = ConversionReport()
        document = read(source(TABLES.replace('<Item>0</Item>', '<Item>8</Item>')), report=report)
        member = document.one('/Board/Tables/Table/RowComponents/Row[1]/Item')
        self.assertEqual(member['UnresolvedComponentIndex'], 8)
        with self.assertRaises(ReferenceError):
            member['Component']
        member['Component'] = document.one('/Board/Components/Component')
        self.assertIsNone(member.child('UnresolvedComponentIndex'))
        self.assertFalse(document.references.issues)
        self.assertIn('unresolved-table-component', [item.rule for item in report.warnings])
        document.references.validate()

    def test_defaults_remain_independent_of_the_display_length_unit(self):
        table = '''<Tables><Table><ColWidths/><RowHeights/><Cells/></Table></Tables>'''
        document = read(source(table).replace('Units="mm"', 'Units="inch"', 1), report=ConversionReport())
        current = document.one('/Board/Tables/Table')
        self.assertEqual((current['Name'], current['DefFontName'], current['DefFontSize']), ('Table', 'Tahoma', 8))
        self.assertEqual((current['DefCellWidth'], current['DefCellHeight'], current['X2'], current['Y2']), (45, 12, 90, 24))
        self.assertEqual((current['DefFontWidth'], current['DefLineSpacing']), (-2, Decimal('1.2')))

    def test_malformed_grid_and_noninteger_component_members_are_rejected(self):
        for text in (TABLES.replace('<Item>3</Item></RowHeights>', '</RowHeights>'),
                     TABLES.replace('<Item>0</Item>', '<Item>0.5</Item>')):
            with self.assertRaises(ValueError):
                read(source(text), report=ConversionReport())


if __name__ == '__main__':
    unittest.main()
