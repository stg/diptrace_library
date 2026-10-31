"""ASC table projection regenerates syntax from current data and relationships."""
import unittest

from lib.common.asc import dumps
from lib.common.conversion import ConversionReport
from lib.common.model import Document
from lib.pcb.formats.asc.table_projection import project_table, project_tables
from lib.pcb.tests.test_non_signal_layers import read as read_layers, source as layer_source
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_table_relations import source, member
from lib.pcb.tests.test_table_model import design


def signature(table):
    result = {}
    for node in table.walk(include_self=True):
        if node.schema is None:
            continue
        path = node.path.removeprefix(table.path)
        for name, field in node.schema.fields.items():
            value = node.get(name)
            if field.kind == 'reference' and value is not None:
                value = value['RefDes'] if value.kind == 'Component' else value.path
            result[path+'/'+name] = value
    return result


def reimport(projected, *, reorder=False):
    data = source()
    data.one('/Board/Tables/Table').detach()
    data.one('/Board/Tables').append(projected)
    if reorder:
        data.one('/Board/Components/Component[1]').move_to(data.one('/Board/Components'), 1)
    return design(data)


def asc_text(table):
    document = Document(representation='asc')
    document.root.append(table.clone())
    return dumps(document, preserve=False)


class TableProjectionTests(unittest.TestCase):
    def test_collection_composition_keeps_order_and_uses_current_group_and_component_indices(self):
        document = design(source())
        table = document.one('/Board/Tables/Table')
        copied = document.copy(table, parent=table.parent)
        copied['Name'] = 'Other table'
        copied.move_to(table.parent, 0)
        output = project_tables(document.one('/Board'))
        self.assertEqual([row['Name'] for row in output.children()], ['Other table', 'Parts'])
        self.assertEqual([row['Group'] for row in output.children()], [0, 0])
        self.assertEqual(output.one('Table[1]/Row_Components/RowCom[2]/pt').values, (0,))

    def test_absent_remembered_layer_is_not_replaced_with_a_real_layer(self):
        document = read_layers(layer_source(table_layer='Top Assy'), report=ConversionReport())
        table = document.one('/Board/Tables/Table')
        table['NonSignalLayer'] = None
        projected = project_table(table)
        self.assertEqual(projected['NonSignal'], -1)
        self.assertIsNone(table['NonSignalLayer'])
        # Both syntax and import keep the explicit absence with real layers present.
        data = source()
        layers = data.one('/Board').add('NonSignals')
        layers.add('NonSignal', 'Notes', 123, 0, 0)
        data.one('/Board/Tables/Table/NonSignal').set_values(projected['NonSignal'])
        self.assertIsNone(design(data).one('/Board/Tables/Table')['NonSignalLayer'])

    def test_unresolved_remembered_layer_is_retained_and_warned(self):
        document = read_layers(layer_source(table_layer='Top Assy', table_key=99), report=ConversionReport())
        report = ConversionReport()
        projected = project_table(document.one('/Board/Tables/Table'), report=report)
        self.assertEqual(projected['NonSignal'], 99)
        self.assertEqual([notice.rule for notice in report.warnings], ['unresolved-non-signal-layer'])

    def test_current_grid_text_style_and_settings_round_trip_through_asc(self):
        document = design(source())
        table = document.one('/Board/Tables/Table')
        table['Group'] = None
        cell = table.one('Cells/Cell[1]')
        cell['Text'] = 'Edited\n\nlast line'
        cell['X2'] = 7
        table.one('AutoUpdate/Columns/Column')['Name'] = 'Quantity'
        before = signature(table)
        report = ConversionReport()
        projected = project_table(table, report=report)
        self.assertEqual(projected.values, ())
        self.assertEqual(projected.one('Cells/Cell[1]').values, (2, 0, 0, 0, 0, 7, 3))
        self.assertEqual(projected.one('Cells/Cell[1]/TextLines/TextLine[2]').values, ('',))
        self.assertEqual(projected.one('Row_Components/RowCom[2]/pt').values, (0,))
        current = reimport(projected).one('/Board/Tables/Table')
        self.assertEqual(signature(current), before)
        self.assertEqual(signature(table), before)
        self.assertEqual(report.notices, [])

    def test_renames_reorders_and_group_indices_come_from_current_identities(self):
        document = design(source())
        table = document.one('/Board/Tables/Table')
        first = document.one('/Board/Components/Component[1]')
        first['RefDes'] = 'R8'
        first.move_to(first.parent, 1)
        projected = project_table(table)
        self.assertEqual(projected.one('Group').values, (0,))
        self.assertEqual(projected.one('Row_Components/RowCom[2]/pt').values, (1,))
        table['Group'] = None
        current = reimport(project_table(table), reorder=True)
        self.assertEqual(member(current)['Component']['RefDes'], 'R003')
        self.assertEqual(member(current)['ComponentIndex'], 1)

    def test_lf_space_normalization_is_detached_and_stable_on_repeated_conversion(self):
        document = design(source())
        table = document.one('/Board/Tables/Table')
        table['Group'] = None
        cell = table.one('Cells/Cell[1]')
        cell['Text'] = 'First\n\t\nLast\n  \n'
        projected = project_table(table)
        self.assertEqual(cell['Text'], 'First\n\t\nLast\n  \n')
        self.assertEqual(projected.one('Cells/Cell[1]/Text').values, ('First\n\t\nLast',))
        current = reimport(projected).one('/Board/Tables/Table')
        self.assertEqual(asc_text(project_table(current)), asc_text(projected))

    def test_unknown_members_remain_explicit_and_are_not_replaced_by_a_source_key(self):
        document = design(source(17))
        table = document.one('/Board/Tables/Table')
        table['Group'] = None
        projected = project_table(table)
        self.assertEqual(projected.one('Row_Components/RowCom[2]/pt').values, (17,))
        self.assertIsNone(projected.child('UnresolvedComponentIndex'))
        current = reimport(projected)
        self.assertEqual(member(current)['UnresolvedComponentIndex'], 17)
        self.assertEqual(len(current.references.issues), 1)

    def test_known_output_omissions_warn_and_leave_authored_values_intact(self):
        document = design(source())
        table = document.one('/Board/Tables/Table')
        column = table.one('AutoUpdate/Columns/Column')
        column['Title'] = 'Order quantity'
        table['DefFontMono'] = True
        cell = table.one('Cells/Cell[1]')
        cell['FontMono'] = True
        report = ConversionReport()
        projected = project_table(table, report=report)
        self.assertEqual({notice.rule for notice in report.warnings},
                         {'table-column-title', 'table-font-monospace'})
        self.assertIsNone(projected.child('DefFontMono'))
        self.assertIsNone(projected.child('Cells/Cell[1]/FontMono'))
        self.assertEqual((column['Title'], table['DefFontMono'], cell['FontMono']),
                         ('Order quantity', True, True))

    def test_unknown_content_and_incomplete_grid_fail_without_changing_the_model(self):
        for extra in (False, True):
            document = design(source())
            table = document.one('/Board/Tables/Table')
            if extra:
                table.add('UnmappedSetting', 'keep me')
            else:
                document.remove(table.one('Cells/Cell[4]'))
            before = dumps(document, preserve=False)
            with self.subTest(extra=extra), self.assertRaises(PcbError):
                project_table(table)
            self.assertEqual(dumps(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
