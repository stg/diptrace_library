"""Both PCB table inputs share editable cells, geometry and current text."""
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib.common import cell_records
from lib.common.asc import dumps
from lib.common.model import Element
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.dip.read import Reader
from lib.pcb.formats.dip.table_model import modernize_tables
from lib.pcb.formats.dip.tables import read_base_tables
from lib.pcb.formats.errors import PcbError
from lib.pcb.model.definitions import definition
from lib.pcb.tests.test_asc_graphics import fixture as graphic_fixture
from lib.pcb.tests.test_tables import table_fixture
from lib.schematic.model.definitions import CELL as SCHEMATIC_CELL


def fixture():
    source = graphic_fixture()
    table = source.one('/Board').add('Tables').add('Table')
    for name, value in dict(Enabled='Y', Selected='N', Locked='N', DefVectorFont='Y',
            HideBorder='N', PanelExclude='N', Layer=0, DefAlign=1, DefFontSize=3,
            DefFontColor=123, DefCellWidth=4, DefCellHeight=3, DefFontWidth=-2,
            DefFontScale=1, DefLineSpacing=0, DefFontName='Arial', Name='Parts',
            X1=0, Y1=0, X2=8, Y2=6, Orientation=0, Group=5, DocType=0, DocUnits=0,
            NonSignal=0, Supplier='', DocSettings_AssemblyVariant=0, DocSettings_RowType=0,
            DocSettings_PickOff_X=0, DocSettings_PickOff_Y=0, DocSettings_Header='Y',
            DocSettings_RowNumber='N', DocSettings_Total='N', DocSettings_PickMirror='N',
            DocSettings_PickOrigin='N', DocSettings_AssemblyName='', DocSettings_Separator='.').items():
        table.add(name, value)
    columns = table.add('DocSettings_Columns', 1)
    column = columns.add('DocSettings_Column')
    for name, value in dict(Type=2, Align=1, Width=8, Name='Value').items():
        column.add(name, value)
    members = table.add('Row_Components', 2)
    members.add('RowCom', 0)
    members.add('RowCom', 1).add('pt', 0)
    for name in ('ColWidths', 'RowHeights'):
        sizes = table.add(name)
        for value in (4, 4) if name == 'ColWidths' else (3, 3):
            sizes.add('pt', value)
    cells = table.add('Cells', 2)
    for column in range(2):
        for row in range(2):
            cell = cells.add('Cell', 2, column, row, column*4, row*3, (column+1)*4, (row+1)*3)
            for name, value in dict(FOrientation='N', FontSize=3, FontType=0, Align=1,
                    FontColor=0, Text='compatibility text', FontName='Arial', VectorFont='Y',
                    FontWidth=-2, FontScale=1, LineSpacing=Decimal('1.2')).items():
                cell.add(name, value)
            lines = cell.add('TextLines')
            for line in ('Current', '', 'value', '   '):
                lines.add('TextLine', line)
    return source


def design(source=None):
    return assemble_graphics(prepare_core(dumps(source or fixture(), preserve=False))).document


class TableModelTests(unittest.TestCase):
    def test_cells_use_the_shared_schematic_record_and_one_authoritative_text(self):
        document = design()
        table = document.one('/Board/Tables/Table')
        cell = table.one('Cells/Cell[1]')
        self.assertIs(cell.schema, cell_records.CELL)
        self.assertIs(cell.schema, SCHEMATIC_CELL)
        self.assertIs(table.one('ColWidths/pt[1]').schema, cell_records.COLUMN_WIDTH)
        self.assertEqual((table['DefFontName'], table['DefLineSpacing']), ('Arial', 0))
        self.assertEqual(cell['Text'], 'Current\n\nvalue')
        self.assertIsNone(cell.child('TextLines'))
        self.assertIsNone(cell.child('TextLine'))
        self.assertEqual(cell.values, (0, 0, 4, 3))
        self.assertEqual([(c['Column'], c['Row']) for c in table.select('Cells/Cell')],
                         [(0, 0), (0, 1), (1, 0), (1, 1)])
        self.assertIs(table['Group'], document.one('/Board/Groups/Group'))

    def test_data_edits_and_grid_positions_need_no_rebuild_or_global_scan(self):
        document = design()
        table = document.one('/Board/Tables/Table')
        cell = table.one('Cells/Cell[1]')
        with patch.object(document.root, 'walk', side_effect=AssertionError('global scan')):
            cell['Text'] = 'Changed'
            cell['X2'] = 9
            cell.move_to(cell.parent, 3)
            self.assertEqual((cell['Text'], cell['X2'], cell['Column'], cell['Row']), ('Changed', 9, 1, 1))
            table['DefFontSize'] = 4
        clone = document.clone()
        self.assertIs(clone.one('/Board/Tables/Table/Cells/Cell[1]').schema, cell_records.CELL)
        self.assertEqual(clone.one('/Board/Tables/Table/Cells/Cell[4]')['Text'], 'Changed')

    def test_documentation_settings_and_row_members_are_typed(self):
        table = design().one('/Board/Tables/Table')
        update = table.one('AutoUpdate')
        self.assertTrue(update['Header'])
        column = update.one('Columns/Column')
        self.assertEqual((column['Index'], column['Type'], column['TextAlign'], column['Width']), (0, 2, 1, 8))
        column['Name'] = 'Quantity'
        self.assertEqual(column['Name'], 'Quantity')
        member = table.one('RowComponents/Row[2]/Item')
        self.assertEqual(member['ComponentIndex'], 0)
        self.assertIs(member['Component'], table._owner().one('/Board/Components/Component'))
        self.assertIsNone(table.child('DocSettings_Header'))

    def test_source_version_does_not_apply_binary_defaults_to_named_current_asc(self):
        source = fixture()
        source.one('/Source').set_argument(1, 31)
        self.assertEqual(design(source).one('/Board/Tables/Table')['DefLineSpacing'], 0)

    def test_binary_bounds_and_defaults_become_current_fields(self):
        for version in (31, 46, 47, 62):
            with self.subTest(version=version):
                board = Element('Board')
                reader = Reader(table_fixture(version))
                table = read_base_tables(reader, board).one('Table')
                if version >= 47:
                    table.add('DefLineSpacing', Decimal('1.6'))
                    for cell in table.select('Cells/Cell'):
                        cell.add('LineSpacing', Decimal('1.4'))
                modernize_tables(SimpleNamespace(board=board, header=reader.header))
                for node in board.walk(include_self=True):
                    if (schema := definition(node)) is not None:
                        node.bind_schema(schema)
                cell = table.one('Cells/Cell[1]')
                self.assertIs(cell.schema, cell_records.CELL)
                self.assertEqual((cell['Column'], cell['Row']), (0, 0))
                self.assertEqual((cell['X1'], cell['Y1'], cell['X2'], cell['Y2']), (0, 0, 4, 3))
                self.assertIsNone(cell.child('Placement'))
                self.assertIsNone(table.child('FontName'))
                self.assertEqual(table['DefFontName'], 'Arial')
                self.assertEqual(table['DefLineSpacing'], Decimal('1.2' if version < 47 else '1.6'))
                self.assertEqual(cell['LineSpacing'], Decimal('1.2' if version < 47 else '1.4'))
                if version < 43:
                    self.assertEqual((table['DocType'], table['DocUnits']), (0, 0))
                if version < 50:
                    self.assertEqual(table.one('AutoUpdate')['Separator'], '.')
                    self.assertEqual(table.one('AutoUpdate/Columns').children(), [])

    def test_bad_counts_positions_bounds_and_booleans_are_rejected(self):
        for field, values in (
                ('Cells', (3,)), ('Cells/Cell[1]', (2, 0, 1, 0, 0, 4, 3)),
                ('Cells/Cell[1]', (2, 0, 0, 'bad', 0, 4, 3)),
                ('Cells/Cell[1]/FOrientation', ('maybe',)), ('DocSettings_Columns', (2,))):
            source = fixture()
            source.one('/Board/Tables/Table/'+field).set_values(*values)
            with self.subTest(field=field), self.assertRaises(PcbError):
                prepare_core(dumps(source, preserve=False))


if __name__ == '__main__':
    unittest.main()
