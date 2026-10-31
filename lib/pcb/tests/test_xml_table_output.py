"""PCB XML documentation grids retain text and current component relationships."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps as model_text
from lib.common.conversion import ConversionReport
from lib.common.units import XmlUnits
from lib.pcb.formats.dipxml.syntax import dumps
from lib.pcb.formats.dipxml.table_output import project_tables
from lib.pcb.formats.errors import PcbError
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import read
from lib.pcb.tests.test_dipxml_tables import source, TABLES
from lib.pcb.tests.test_xml_routing_output import context, with_component_library


def design(text=None):
    return read(with_component_library(source() if text is None else text), report=ConversionReport())


def reopen(document, *, units='mm', report=None):
    output, _ = context(document, units=units, report=report)
    output.one('/Source/Board').append(project_tables(document.one('/Board'), units=XmlUnits(units), report=report))
    return read(dumps(output), report=ConversionReport()), output


class XmlTableOutputTests(unittest.TestCase):
    def assert_facts(self, actual, expected):
        self.assertEqual(actual.keys(), expected.keys())
        for name, value in expected.items():
            if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                self.assertLessEqual(abs(actual[name]-value), Decimal('1e-23'), name)
            else:
                self.assertEqual(actual[name], value, name)

    def test_tables_text_styles_documentation_options_and_geometry_survive_units(self):
        document = design()
        expected, before = signature(document.one('/Board/Tables')), model_text(document, preserve=False)
        for units in ('mm', 'mil', 'inch'):
            current = document
            for _ in range(3):
                current, _ = reopen(current, units=units)
                self.assert_facts(signature(current.one('/Board/Tables')), expected)
                current.references.validate()
        self.assertEqual(model_text(document, preserve=False), before)

    def test_component_row_members_follow_reordering_without_stored_positions(self):
        document = design()
        original = document.one('/Board/Components/Component')
        document.copy(original, parent=original.parent, index=0, fields={'RefDes': 'U2'})
        expected = signature(document.one('/Board/Tables'))
        current, _ = reopen(document)
        self.assert_facts(signature(current.one('/Board/Tables')), expected)
        member = current.one('/Board/Tables/Table/RowComponents/Row[1]/Item')
        self.assertIs(member['Component'], current.one('/Board/Components/Component[2]'))
        current.references.validate()

    def test_known_text_option_omissions_warn_and_leave_source_unchanged(self):
        document = design()
        table, cell = document.one('/Board/Tables/Table'), document.one('/Board/Tables/Table/Cells/Cell[1]')
        table['DefFontColor'], cell['FontColor'] = 123, 456
        cell['FOrientation'], cell['FontType'] = True, 1
        report, before = ConversionReport(), model_text(document, preserve=False)
        current, _ = reopen(document, report=report)
        self.assertEqual(current.one('/Board/Tables/Table/Cells/Cell[1]')['Text'], cell['Text'])
        self.assertTrue({'table-font-color', 'table-cell-text-mode'} <= {notice.rule for notice in report.warnings})
        self.assertEqual(model_text(document, preserve=False), before)

    def test_unresolved_component_positions_remain_unresolved_with_a_warning(self):
        document = design(source(TABLES.replace('<Item>0</Item>', '<Item>8</Item>')))
        report = ConversionReport()
        current, _ = reopen(document, report=report)
        member = current.one('/Board/Tables/Table/RowComponents/Row[1]/Item')
        self.assertEqual(member['UnresolvedComponentIndex'], 8)
        self.assertIn('unresolved-table-component', {notice.rule for notice in report.warnings})

    def test_unsupported_or_incomplete_table_data_is_an_atomic_failure(self):
        for kind in ('unmapped', 'rectangle', 'inactive'):
            with self.subTest(kind=kind):
                document = design()
                table = document.one('/Board/Tables/Table')
                if kind == 'unmapped':
                    table.add('UnmappedTableSetting', 3)
                elif kind == 'rectangle':
                    table.one('Cells/Cell[1]').detach()
                else:
                    for member in table.select('RowComponents/Row/Item'):
                        member['Component'] = None
                    table['Enabled'] = False
                before = model_text(document, preserve=False)
                with self.assertRaises((PcbError, ValueError)):
                    reopen(document)
                self.assertEqual(model_text(document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
