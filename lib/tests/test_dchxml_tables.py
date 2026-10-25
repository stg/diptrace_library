"""Table grids and title fields use distinct public units and editable links."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import parse_dchxml, ReferenceError
from lib.schematic.formats.dchxml.tables import (project_table, project_title_block)
from lib.common.units import XmlUnits
from lib.common.model import (Element)


def style(node, prefix=''):
    for name, value in dict(FontSize=9, FontType=0, FontColor=123, FontName='Vector',
                             VectorFont=True, FontWidth=3, FontScale=1, LineSpacing=1.2).items():
        node.add(prefix+name, value)


class XmlTablesTests(unittest.TestCase):
    def test_table_grid_is_column_major_and_table_font_width_is_unscaled(self):
        table = Element('Table')
        for name, value in dict(HideBorder=True, Page=2, Orientation=1, DefCellWidth=6,
             DefCellHeight=9, DefAlign=2, Group=-1, Name='BOM', Selected=False, Locked=True,
             X1=3, Y1=6, X2=30, Y2=60).items():
            table.add(name, value)
        style(table, 'Def')
        for name, values in (('ColWidths', (12, 15)), ('RowHeights', (18, 21))):
            parent = table.add(name)
            for value in values:
                parent.add('pt', value)
        cells = table.add('Cells')
        for index in range(4):
            cell = cells.add('Cell', 3, 6, 9, 12)
            style(cell)
            cell.add('Align', 0)
            cell.add('Text', str(index)+'\nsecond\n  \n')
        result = project_table(table, index=7, units=XmlUnits('mm'))
        self.assertEqual((result.scalar('Orientation'), result.scalar('FontWidth'), result.scalar('Y1')), (90, 3, -2))
        self.assertEqual([[cell.select('TextLines/TextLine')[0].values[0] for cell in column.children('Cell')]
                          for column in result.select('Cells/Cell')], [['0', '1'], ['2', '3']])
        self.assertEqual(result.one('Cells/Cell[1]/Cell[1]').scalar('FontWidth'), 3)
        self.assertEqual(result.one('Cells/Cell[1]/Cell[1]').scalar('Y2'), -4)
        cells.children()[0].detach()
        with self.assertRaisesRegex(ValueError, 'declared rectangle'):
            project_table(table, index=7, units=XmlUnits('mm'))

    def test_title_font_width_is_physical_and_fields_preserve_text(self):
        grid = Element('TitleBlock', 0, 'Custom')
        grid.add('Width', 30)
        grid.add('Height', 15)
        grid.add('ColWidths').add('pt', 30)
        grid.add('RowHeights').add('pt', 15)
        grid.add('Cells').add('Cell', 0, 0, 0).add('Edges', True, False, True, False)
        content = grid.add('Contents').add('Content', 0)
        style(content)
        content.add('Text', 'Title\n\nRevision\n')
        content.add('Align', 1)
        content.add('Placement', 3, 6, 9, 12)
        result = project_title_block(grid, name='BottomRightBlock', units=XmlUnits('mm'))
        field = result.one('Fields/Field')
        self.assertEqual((field.scalar('FontWidth'), field.scalar('TextShow')), (1, 'Text'))
        self.assertEqual([line.values for line in field.select('TextLines/TextLine')], [('Title',), (), ('Revision',)])
        self.assertEqual(result.one('Cells/Item/Item').scalar('BottomLine'), False)
        content.set_field('FontWidth', -1)
        result = project_title_block(grid, name='BottomRightBlock', units=XmlUnits('mm'))
        self.assertEqual(result.one('Fields/Field').scalar('FontWidth'), -1)

    def test_title_cell_field_links_follow_key_edits_and_reject_other_blocks(self):
        document = parse_dchxml('''<Source Type="DipTrace-Schematic"><Schematic><SheetSettings><Sheets><Sheet><Id>0</Id>
        <BottomRightBlock><Cells><Item><Item FieldId="4" TopLine="Y"/></Item></Cells><Fields><Field Id="4"/></Fields></BottomRightBlock>
        <TopLeftBlock><Fields><Field Id="5"/></Fields></TopLeftBlock>
        </Sheet></Sheets></SheetSettings></Schematic></Source>''')
        block = document.one('/Source/Schematic/SheetSettings/Sheets/Sheet/BottomRightBlock')
        block.one('Fields/Field').set_field('Id', 41)
        document.rebuild()
        cell = block.one('Cells/Item/Item')
        self.assertEqual(cell.scalar('FieldId'), 41)
        reference = document.references.outgoing(cell, role='xml-title-field')[0]
        document.references.retarget(reference, block.parent.one('TopLeftBlock/Fields/Field'))
        with self.assertRaisesRegex(ReferenceError, 'outside its local title block'):
            document.rebuild()


if __name__ == '__main__':
    unittest.main()
