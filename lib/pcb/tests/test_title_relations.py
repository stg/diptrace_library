"""Sheet cells select editable field identities, rather than saved positions."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import Property, ReferenceError
from lib.common.title_records import TITLE_FIELD, new_title_blocks
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.model import title_records
from lib.pcb.model.title_relations import MISSING, ROLE
from lib.pcb.tests.test_dipxml_electrical import prepared
from lib.pcb.tests.test_dipxml_settings import source as settings_source


GRID = '''<BottomRightBlock Width="20" Height="6"><Name>Revision</Name>
  <ColumnWidths><Item>20</Item></ColumnWidths><RowHeights><Item>3</Item><Item>3</Item></RowHeights>
  <Fields>
    <Field Id="42" TextShow="Text" TextAlign="Right" X1="1" Y1="2" X2="3" Y2="4"
           FontVector="Y" FontSize="5" FontSizeFloat="5.5" FontColor="123" FontWidth="0.2"
           FontScale="1.1" LineSpacing="1.3"><FontName>Vector</FontName>
      <TextLines><TextLine>Revision</TextLine><TextLine>A</TextLine></TextLines></Field>
    <Field Id="9" TextShow="Sheet"><TextLines><TextLine>Sheet</TextLine></TextLines></Field>
  </Fields>
  <Cells><Item><Item FieldId="42" TopLine="Y" BottomLine="N" LeftLine="Y" RightLine="N"/>
    <Item FieldId="9" TopLine="N" BottomLine="Y" LeftLine="N" RightLine="Y"/></Item></Cells>
</BottomRightBlock>'''


def source():
    return settings_source().replace('</SheetSettings>', GRID+'</SheetSettings>')


def design(data=None):
    return assemble_rules(prepared(source()) if data is None else data).document


def grid(document):
    return document.one('/Board/SheetSettings/TitleBlocks/TitleBlock[1]')


def cell(document):
    return grid(document).one('Cells/Cell[1]')


class PcbTitleTests(unittest.TestCase):
    def test_xml_keys_are_consumed_into_shared_fields_and_grid_local_links(self):
        document = design()
        block = grid(document)
        first, second = block.select('Contents/Content')
        self.assertIs(first.schema, TITLE_FIELD)
        self.assertEqual((block['Position'], block['Name'], block['Width'], block['Height']),
                         (0, 'Revision', 60, 18))
        self.assertEqual([row['Height'] for row in block.select('RowHeights/pt')], [9, 9])
        self.assertEqual(first['Text'], 'Revision\nA')
        self.assertEqual((first['FontSize'], first['FontWidth'], first['FontScale']),
                         (Decimal('5.5'), Decimal('.6'), Decimal('1.1')))
        self.assertEqual(first['Placement'], (3, -6, 9, -12))
        self.assertEqual((first['Align'], second['FontType']), (2, 1))
        self.assertIs(cell(document)['Field'], first)
        self.assertIs(block.one('Cells/Cell[2]')['Field'], second)
        self.assertEqual(cell(document).values, (0, 0, 0))
        self.assertIsNone(cell(document).child('FieldId'))
        self.assertEqual(cell(document)['Edges'], (True, False, True, False))
        document.references.validate()

    def test_reorder_and_retarget_update_dependents_without_global_scans(self):
        document = design()
        first, second = grid(document).select('Contents/Content')
        selected = cell(document)
        probe = document.root.add('Probe', 0)
        document.references.bind(probe, selected, Property(probe, 'FieldId'), role='probe')
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            first.move_to(first.parent, 1)
            self.assertEqual((first['Index'], selected['FieldId'], probe.values), (1, 1, (1,)))
            selected['Field'] = second
            self.assertEqual((selected['FieldId'], probe.values), (0, (0,)))
            selected['Field'] = None
            self.assertIsNone(selected['Field'])
            self.assertEqual((selected['FieldId'], probe.values), (-1, (-1,)))
        with self.assertRaises(TypeError):
            selected['FieldId'] = 0

    def test_target_and_ownership_constraints_are_atomic(self):
        document = design()
        selected = cell(document)
        original = selected['Field']
        other = document.one('/Board/SheetSettings/TitleBlocks/TitleBlock[2]/Contents')
        other_field = other.add('Content')
        self.assertIs(other_field.schema, TITLE_FIELD)
        for target in (other_field, cell(design())['Field'], document.one('/Board')):
            with self.subTest(target=target.path), self.assertRaises(ReferenceError):
                selected['Field'] = target
            self.assertIs(selected['Field'], original)
        with self.assertRaises(ReferenceError):
            document.references.bind(selected, original, role=ROLE)
        with self.assertRaises(ReferenceError):
            document.remove(original)
        with self.assertRaises(ReferenceError):
            original.move_to(other)
        with self.assertRaises(ReferenceError):
            selected.move_to(other.parent.one('Cells'))
        self.assertIs(selected['Field'], original)
        document.references.validate()

    def test_clone_copy_and_new_cells_keep_identity_ownership(self):
        document = design()
        block, original = grid(document), cell(document)
        clone = document.clone()
        self.assertIs(cell(clone)['Field'], grid(clone).one('Contents/Content[1]'))
        self.assertIsNot(cell(clone)['Field'], original['Field'])
        copied = document.copy(original)
        self.assertIs(copied['Field'], original['Field'])
        copied_field = document.copy(original['Field'])
        copied_field['Text'] = 'Independent'
        self.assertEqual(original['Field']['Text'], 'Revision\nA')
        new = block.one('Cells').add('Cell')
        self.assertIs(new.schema, title_records.CELL)
        self.assertIsNone(new['Field'])
        new['Field'] = copied_field
        self.assertEqual(new['FieldId'], 2)
        with self.assertRaises(TypeError):
            block.one('Cells').add('Cell', 0, 0, 0)
        with self.assertRaises(ReferenceError):
            document.copy(original, parent=document.one('/Board/Components'))
        document.references.validate()

    def test_unavailable_binary_position_is_explicit_and_scope_guarded(self):
        data = prepared(source())
        data.board.one('SheetSettings/TitleBlocks/TitleBlock[1]/Cells/Cell[1]').set_argument(2, 17)
        report = ConversionReport()
        document = import_diagnostics('dip')(design)(data, report=report)
        selected = cell(document)
        self.assertEqual((selected[MISSING], selected['FieldId']), (17, 17))
        self.assertIn('unresolved-title-field', {notice.rule for notice in report.warnings})
        with self.assertRaisesRegex(ReferenceError, 'unresolved'):
            _ = selected['Field']
        with self.assertRaises(ReferenceError):
            grid(document).one('Contents/Content[1]').move_to(grid(document).one('Contents'), 1)
        with self.assertRaisesRegex(ValueError, 'reference-managed'):
            selected[MISSING] = 0
        grid(document).one('Contents/Content[1]')['Text'] = 'Independent edit'
        clone = document.clone()
        self.assertEqual(cell(clone)[MISSING], 17)
        self.assertIs(clone.references.issues[0].source, cell(clone))
        document.references.validate()
        clone.references.validate()

    def test_replacing_title_grids_establishes_shared_records_and_empty_anchors(self):
        document = design()
        sheet = document.one('/Board/SheetSettings')
        document.remove(sheet.one('TitleBlocks'))
        titles = sheet.append(new_title_blocks())
        self.assertIs(titles.schema, title_records.BLOCKS)
        self.assertEqual(len(titles.children('TitleBlock')), 6)
        for index, block in enumerate(titles.children('TitleBlock')):
            self.assertIs(block.schema, title_records.BLOCK)
            self.assertEqual((block['Position'], block['Name']), (index, ''))
        self.assertFalse(any(link.role == ROLE for link in document.references))
        document.references.validate()

    def test_unavailable_selection_repair_and_disconnect_are_atomic(self):
        for disconnect in (False, True):
            with self.subTest(disconnect=disconnect):
                data = prepared(source())
                data.board.one('SheetSettings/TitleBlocks/TitleBlock[1]/Cells/Cell[1]').set_argument(2, 17)
                document = design(data)
                selected = cell(document)
                probe = document.root.add('Probe', 17)
                document.references.bind(probe, selected, Property(probe, 'FieldId'))
                with self.assertRaises(ReferenceError):
                    selected['Field'] = cell(design())['Field']
                self.assertEqual((selected[MISSING], probe.values, len(document.references.issues)), (17, (17,), 1))
                target = None if disconnect else grid(document).one('Contents/Content[2]')
                selected['Field'] = target
                self.assertIs(selected['Field'], target)
                self.assertIsNone(selected.child(MISSING))
                self.assertEqual(probe.values, (-1 if disconnect else 1,))
                self.assertEqual(document.references.issues, [])
                grid(document).one('Contents/Content[1]').move_to(grid(document).one('Contents'), 1)
                document.references.validate()


if __name__ == '__main__':
    unittest.main()
