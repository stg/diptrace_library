"""Named table/title data preserves bounds, ordering and field identities."""
import unittest

from lib import ConversionReport, new_schematic, parse, serialize
from lib.schematic.model.refs import bind_schematic_references
from lib.tests.test_cell_text import table_document
from lib.tests.test_dchxml_tables import style


def title_document():
    doc = new_schematic()
    grid = doc.one('/Schematic/Pages/Page/TitleBlocks/TitleBlock[1]')
    grid['Name'] = 'Custom'
    grid['Width'] = 30
    grid['Height'] = 15
    grid.one('ColWidths').add('pt', 30)
    grid.one('RowHeights').add('pt', 15)
    content = grid.one('Contents').add('Content', 0)
    style(content)
    content.add('Text', 'Title')
    content.add('Align', 1)
    content.add('FOrientation', False)
    content.add('FontMono', False)
    content.add('Placement', 3, 6, 9, 12)
    cell = grid.one('Cells').add('Cell', 0, 0, 0)
    cell.add('Edges', True, False, True, False)
    bind_schematic_references(doc)
    return doc, grid, cell, content


class LayoutSchemaTests(unittest.TestCase):
    def test_cell_bounds_are_editable_and_grid_coordinates_follow_order(self):
        doc = table_document(columns=(4, 5), rows=(5, 6))
        cells = doc.one('/Schematic/Tables/Table/Cells')
        cell = cells.children('Cell')[0]
        self.assertEqual((cell['Column'], cell['Row']), (0, 0))
        cell['Text'] = 'moved'
        cell['X2'] = 9
        cell.move_to(cells, 3)
        self.assertEqual((cell['Column'], cell['Row']), (1, 1))
        with self.assertRaises(TypeError):
            cell['Column'] = 0
        for format in ('dch', 'asc', 'dchxml'):
            current = parse(serialize(doc, format=format, report=ConversionReport()),
                            format=format, report=ConversionReport())
            moved = current.one('//Cell[Text="moved"]')
            self.assertEqual((moved['Column'], moved['Row'], moved['X2']), (1, 1, 9))

    def test_title_position_and_named_borders_cross_binary_and_xml(self):
        doc, grid, cell, content = title_document()
        grid.one('ColWidths/pt')['Width'] = 33
        cell.one('Edges')['BottomLine'] = True
        content.one('Placement')['Y2'] = 18
        grid.move_to(grid.parent, 1)
        self.assertEqual(grid['Position'], 1)
        self.assertEqual(content['Placement'], (3, 6, 9, 18))
        for format in ('dch', 'dchxml'):
            current = parse(serialize(doc, format=format, report=ConversionReport()),
                            format=format, report=ConversionReport())
            restored = current.one('//TitleBlock[Name="Custom"]')
            self.assertEqual(restored['Position'], 1)
            self.assertEqual(restored.one('ColWidths/pt')['Width'], 33)
            self.assertTrue(restored.one('Cells/Cell/Edges')['BottomLine'])
            self.assertEqual(restored.one('Contents/Content/Placement')['Y2'], 18)

    def test_promoted_field_id_remains_managed_and_retargetable(self):
        doc, grid, cell, content = title_document()
        with self.assertRaisesRegex(ValueError, 'reference-managed'):
            cell['FieldId'] = 1
        second = grid.one('Contents').append(content.clone())
        second['Text'] = 'Second'
        reference = doc.references.outgoing(cell, role='title-cell-field')[0]
        doc.references.retarget(reference, second)
        self.assertEqual(cell['FieldId'], 1)
        self.assertEqual(second['Index'], 1)
        doc.validate()
