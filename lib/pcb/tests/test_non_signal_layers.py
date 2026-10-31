"""Custom-layer selections and visibility follow the edited layer identities."""
import unittest
from unittest.mock import patch

from lib.common.asc import loads, dumps
from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import ReferenceError
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.table_projection import project_table
from lib.pcb.formats.dipxml.read import prepare
from lib.pcb.tests.test_asc_core import fixture as asc_fixture
from lib.pcb.tests.test_dipxml_library import source as xml_fixture


LAYERS = '''<NonSignals><NonSignal Id="47" Color="123"><Name>Notes</Name></NonSignal>
  <NonSignal Id="5" Color="456"><Name>Fabrication</Name></NonSignal></NonSignals>'''


def source(*, layers=LAYERS, table_layer='Non-Signal', table_key=47, dim_key=5, visibility=('Y', 'N')):
    panel = '<Settings><LayerPanel>'+''.join('<NonSignal>'+value+'</NonSignal>' for value in visibility)+'</LayerPanel></Settings>'
    objects = f'''<Tables><Table Layer="{table_layer}" NonSignal="{table_key}"/></Tables>
      <Dimensions><Dimension Layer="Non-Signal" NonSignal="{dim_key}" Connected1="None" Connected2="None"/></Dimensions>'''
    return xml_fixture().replace('</Board>', layers+panel+objects+'</Board>')


@import_diagnostics('dipxml')
def read(text):
    return assemble_graphics(prepare(text)).document


class NonSignalLayerTests(unittest.TestCase):
    def test_nonconsecutive_keys_visibility_and_identity_edits(self):
        document = read(source(), report=ConversionReport())
        first, second = document.select('/Board/NonSignals/NonSignal')
        table, dimension = document.one('/Board/Tables/Table'), document.one('/Board/Dimensions/Dimension')
        self.assertIs(table['NonSignalLayer'], first)
        self.assertIs(dimension['NonSignalLayer'], second)
        self.assertEqual((table['NonSignal'], dimension['NonSignal']), (0, 1))
        self.assertEqual((first['Visible'], second['Visible']), (True, False))
        self.assertIsNone(document.one('/Board/Settings/LayerPanel').child('NonSignals'))
        self.assertIsNone(table.child('NonSignal'))
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            second.move_to(second.parent, 0)
            first['Name'] = 'Assembly notes'
            second['Visible'] = True
            self.assertEqual((table['NonSignal'], dimension['NonSignal']), (1, 0))
        projected = project_table(table)
        self.assertEqual(projected['NonSignal'], 1)
        self.assertIsNone(table.child('NonSignal'))
        with self.assertRaises(ReferenceError):
            first.detach()
        with self.assertRaises(TypeError):
            table['NonSignal'] = 0
        copied = document.copy(table, parent=table.parent)
        self.assertIs(copied['NonSignalLayer'], first)
        clone = document.clone()
        cloned_layer = clone.one('/Board/NonSignals/NonSignal[2]')
        self.assertIs(clone.one('/Board/Tables/Table[1]')['NonSignalLayer'], cloned_layer)
        with self.assertRaises(ReferenceError):
            table['NonSignalLayer'] = cloned_layer
        document.references.validate()
        clone.references.validate()

    def test_remembered_selection_remains_meaningful_on_other_layer_families(self):
        document = read(source(table_layer='Top Assy'), report=ConversionReport())
        table = document.one('/Board/Tables/Table')
        layer = document.one('/Board/NonSignals/NonSignal[1]')
        self.assertIs(table['NonSignalLayer'], layer)
        table['Layer'] = 4
        self.assertIs(table['NonSignalLayer'], layer)
        table['Layer'] = 0
        table['NonSignalLayer'] = None
        self.assertEqual(table['NonSignal'], -1)
        self.assertIsNone(table['NonSignalLayer'])

    def test_unavailable_active_selection_uses_last_layer_or_standard_family(self):
        report = ConversionReport()
        document = read(source(table_key=99, dim_key=-1), report=report)
        last = document.one('/Board/NonSignals/NonSignal[2]')
        self.assertIs(document.one('/Board/Tables/Table')['NonSignalLayer'], last)
        self.assertIs(document.one('/Board/Dimensions/Dimension')['NonSignalLayer'], last)
        self.assertFalse(any(notice.rule == 'unresolved-non-signal-layer' for notice in report.warnings))
        self.assertTrue(any(notice.rule == 'non-signal-layer-normalization' for notice in report.infos))
        empty = read(source(layers='', visibility=()), report=ConversionReport())
        self.assertEqual(empty.one('/Board/Tables/Table')['Layer'], 0)
        self.assertEqual(empty.one('/Board/Dimensions/Dimension')['Layer'], 13)
        self.assertIsNone(empty.one('/Board/Tables/Table')['NonSignalLayer'])

    def test_unavailable_remembered_selection_is_explicit_and_repairable(self):
        report = ConversionReport()
        document = read(source(table_layer='Top Assy', table_key=99), report=report)
        table = document.one('/Board/Tables/Table')
        self.assertEqual(table['NonSignal'], 99)
        with self.assertRaises(ReferenceError):
            table['NonSignalLayer']
        self.assertTrue(any(notice.rule == 'unresolved-non-signal-layer' for notice in report.warnings))
        layer = document.one('/Board/NonSignals/NonSignal[1]')
        table['NonSignalLayer'] = layer
        self.assertIsNone(table.child('UnresolvedNonSignal'))
        self.assertIs(table['NonSignalLayer'], layer)
        document.references.validate()

    def test_asc_visibility_rows_join_the_same_current_layer_data(self):
        syntax = loads(asc_fixture())
        board = syntax.one('/Board')
        layers = board.add('NonSignals')
        layers.add('NonSignal', 'Notes', 123, 47, 0)
        layers.add('NonSignal', 'Fabrication', 456, 5, 0)
        visibility = board.add('LayerPanel_NonSignal')
        visibility.add('pt', 'N')
        visibility.add('pt', 'Y')
        loaded = assemble_graphics(prepare_core(dumps(syntax, preserve=False))).document
        self.assertEqual([layer['Visible'] for layer in loaded.select('/Board/NonSignals/NonSignal')], [False, True])
        self.assertIsNone(loaded.one('/Board').child('LayerPanel_NonSignal'))

    def test_visibility_absence_and_extra_capacity_do_not_invent_layers(self):
        report = ConversionReport()
        document = read(source(visibility=('N', 'Y', 'N')), report=report)
        self.assertEqual(len(document.select('/Board/NonSignals/NonSignal')), 2)
        self.assertTrue(any(notice.rule == 'non-signal-display-capacity' for notice in report.infos))
        absent = read(source(visibility=()), report=ConversionReport())
        self.assertIsNone(absent.one('/Board/NonSignals/NonSignal[1]').get('Visible'))
        with self.assertRaisesRegex(ValueError, 'requires Y or N'):
            read(source(visibility=('Maybe',)), report=ConversionReport())

    def test_unnumbered_legacy_layers_resolve_positions_without_saved_identity_copies(self):
        inputs = prepare(source(table_key=0, dim_key=1))
        for layer in inputs.board.select('NonSignals/NonSignal'):
            layer.set_argument(2, -1)
        document = assemble_graphics(inputs).document
        first, second = document.select('/Board/NonSignals/NonSignal')
        self.assertIs(document.one('/Board/Tables/Table')['NonSignalLayer'], first)
        self.assertIs(document.one('/Board/Dimensions/Dimension')['NonSignalLayer'], second)
        self.assertEqual(first.values, ('Notes',))
        new = first.parent.add('NonSignal', 'New notes')
        new['Visible'] = False
        self.assertEqual((new['Name'], new['Visible']), ('New notes', False))
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
