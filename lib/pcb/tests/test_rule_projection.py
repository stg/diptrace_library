"""ASC rule output follows edited identities, not original saved selectors."""
from decimal import Decimal
import unittest

from lib.common.asc import dumps, loads
from lib.common.conversion import ConversionReport
from lib.common.model import Document
from lib.pcb.formats.asc.core import prepare_core
from lib.pcb.formats.asc.rule_projection import project_rules
from lib.pcb.formats.asc.projection import value
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.formats.errors import PcbError
from lib.pcb.formats.output_indices import OutputIndices
from lib.pcb.tests.test_asc_core import fixture as electrical_fixture
from lib.pcb.tests.test_asc_rules import fixture, settings_fixture
from lib.pcb.tests.test_length_rule_inputs import asc_source


def text(node):
    document = Document(representation='asc')
    document.root.append(node.clone())
    return dumps(document, preserve=False)


def current_input(board, projected):
    """Put a section into a neutral electrical input with fresh positive pad keys.

    This fixture supplies the electrical sections whose writer is separate.
    Keeping these old template keys would conceal bad output reference indices.
    """
    syntax = loads(electrical_fixture(units=board._owner().root['Units']))
    target = syntax.one('/Board')
    component = target.one('Components/Component')
    component.one('Number').set_values(0)
    pad_keys = {9: 1, 11: 2}
    for path in ('InternalConnection_Records/pt', 'InternalConnections/IntCon/PadNum/pt',
                 'InternalConnections/IntCon/Line/pt'):
        for row in component.select(path):
            row.set_values(*(pad_keys[number] for number in row.values))
    for index, pad in enumerate(component.one('Pads').children()):
        pad.one('Number').set_values(index if index in (1, 2) else -1)
        selected = pad.one('NetNumber')
        if selected.values[0] >= 0:
            selected.set_values(0)
    net = target.one('Nets/Net')
    net.one('Number').set_values(0)
    for index, row in enumerate(net.one('Component').children(), 1):
        row.set_values(0, index)
    current = board.one('Components/Component')
    component.add('ConnectedLayer', current['ConnectedLayer'])
    component.add('ViaStyle', current['ViaStyle'])
    net.add('NetClass', OutputIndices(board).class_number(board.one('Nets/Net')['Class']))
    for node in tuple(projected.children()):
        target.append(node.clone())
    return prepare_core(dumps(syntax, preserve=False))


def signature(board):
    """Compare current rule meaning, independent of serialization-only ordering."""
    result = {}

    def visit(node, path):
        fields = {}
        for name, definition in node.schema.fields.items():
            if node.kind == 'NetClass' and name == 'Id':
                continue
            current = value(node, name)
            if definition.kind == 'reference':
                current = None if current is None else (current.kind, current.get('Name'))
            elif isinstance(current, tuple):
                current = tuple((part.kind, part.get('Name')) for part in current)
            fields[name] = current
        result[path] = fields
        for name in node.schema.children:
            for child in node.children(name):
                key = child['Layer']['Name'] if 'Layer' in child.schema.fields and child['Layer'] is not None else child._ordinal()
                visit(child, path+f'/{name}/{key}')

    for name in ('Layers', 'ViaStyles', 'NetClasses', 'LayerStackItems', 'LengthRules'):
        source = board.child(name)
        if source is not None:
            for row in source.children():
                key = value(row, 'Name') if 'Name' in row.schema.fields else row._ordinal()
                visit(row, name+'/'+str(key))
    if (main := board.child('MainLengthRule')) is not None:
        visit(main, 'MainLengthRule')
    for name in ('DRC', 'ConnectivityCheck'):
        if (record := board.child(name)) is not None:
            visit(record, name)
    if (routing := board.child('Settings')) is not None and (routing := routing.child('Routing')) is not None:
        visit(routing, 'Routing')
    for cell in board.select('ClassClearances/Cell'):
        pair = tuple(sorted((cell['Class1']['Name'], cell['Class2']['Name'])))
        result['ClassClearances/'+str(pair)] = (
            cell['AllLayers'], value(cell, 'Clearance'),
            tuple(sorted((row['Layer']['Name'], value(row, 'Clearance'))
                         for row in cell.select('LayerClearances/LayerClearance'))))
    return result


class RuleProjectionTests(unittest.TestCase):
    def test_rules_round_trip_without_mutation_or_saved_key_replay(self):
        result = assemble_rules(prepare_core(fixture()))
        board = result.document.one('/Board')
        before = dumps(result.document, preserve=False)
        expected = signature(board)
        report = ConversionReport()
        projected = project_rules(board, report=report)
        self.assertEqual(projected.one('Layers/Name[2]/NetNumber').values, (0,))
        self.assertEqual(projected.one('NetClasses/NetClass[1]/LayProperties/LayProperty/MinWidth').values, (300,))
        self.assertEqual(projected.one('NetClasses/NetClass[1]/LayProperties/LayProperty/MaxWidth').values, (Decimal('.03'),))
        self.assertEqual(projected.one('Layers/Name[1]/HoleSize').values, (Decimal('1.2'),))
        imported = assemble_rules(current_input(board, projected)).document.one('/Board')
        self.assertEqual(signature(imported), expected)
        self.assertEqual(text(project_rules(imported)), text(projected))
        self.assertEqual(dumps(result.document, preserve=False), before)
        self.assertEqual(report.notices, [])
        result.document.references.validate()

    def test_layer_and_class_reorder_regenerate_positions_and_symmetric_cells(self):
        result = assemble_rules(prepare_core(fixture()))
        board = result.document.one('/Board')
        top, plane, bottom = result.layers.values()
        bottom.move_to(bottom.parent, 1)
        signal = result.classes[1]
        signal.move_to(signal.parent, 0)
        top['Name'] = 'Outer top'
        signal['PriorityValue'] = 9
        projected = project_rules(board)
        self.assertEqual(projected.one('Layers/Name[1]').values, ('Outer!top',))
        self.assertEqual(projected.one('ViaStyles/ViaStyle[2]').values[-2:], (0, 2))
        self.assertEqual([row.one('Width').values[0] for row in
                         projected.select('NetClasses/NetClass[2]/LayProperties/LayProperty')], [1, 3, 2])
        matrix = projected.one('CTC_Cells')
        self.assertEqual(matrix.values, (2,))
        self.assertEqual(len(matrix.children()), 4)
        off_diagonal = [row for row in matrix.children() if row.values[:2] in ((0, 1), (1, 0))]
        self.assertEqual([[row.values for row in cell.children()] for cell in off_diagonal],
                         [[(Decimal('.1'),), (Decimal('.3'),), (Decimal('.2'),)]]*2)
        self.assertEqual(projected.one('LayerStack').values, ('Three copper layers', 7))
        self.assertEqual([row.values[0] for row in projected.one('LayerStack').children()], [-1, 0, -1, 2, -1, 1, -1])
        imported = assemble_rules(current_input(board, projected)).document.one('/Board')
        self.assertEqual(signature(imported), signature(board))
        self.assertIs(board['DefaultClass'], result.classes[0])

    def test_routing_aliases_current_drc_and_connectivity_share_the_rule_output(self):
        result = assemble_rules(prepare_core(settings_fixture()))
        board = result.document.one('/Board')
        routing = board.one('Settings/Routing')
        routing['TraceWidth'] = Decimal('0.7498')
        routing['TraceClearance'] = Decimal('0.3749')
        drc = board.one('DRC')
        drc['SilkClearance'] = Decimal('0.8')
        drc.one('LayClearances/LayClearance/ClearanceDetails')['ViaToBoard'] = Decimal('0.3')
        projected = project_rules(board)
        settings = projected.one('Settings')
        self.assertEqual(settings.one('TraceWidth').values, (Decimal('0.7498'),))
        self.assertEqual(settings.one('DRC_Name').values, ('N',))
        self.assertEqual(settings.one('DRC_CheckPours').values, ('Y',))
        self.assertEqual(settings.one('DRC_LayClearances/DRC_LayClearance/pt[2]').values[-1], Decimal('0.3'))
        imported = assemble_rules(current_input(board, projected)).document.one('/Board')
        self.assertEqual(signature(imported), signature(board))
        self.assertEqual(text(project_rules(imported)), text(projected))

    def test_default_class_reorder_keeps_routing_defaults_and_class_selection(self):
        result = assemble_rules(prepare_core(settings_fixture()))
        board = result.document.one('/Board')
        result.classes[1].move_to(result.classes[1].parent, 0)
        report = ConversionReport()
        projected = project_rules(board, report=report)
        self.assertEqual(projected.one('NetClasses/NetClass[1]').values, ('Default',))
        self.assertEqual([notice.rule for notice in report.infos], ['default-class-order'])
        imported = assemble_rules(current_input(board, projected)).document.one('/Board')
        self.assertEqual(imported['DefaultClass']['Name'], 'Default')
        self.assertEqual(imported.one('Nets/Net')['Class']['Name'], 'Signal')
        self.assertEqual(signature(imported), signature(board))

    def test_class_policy_results_and_user_policies_keep_current_meaning(self):
        result = assemble_rules(prepare_core(asc_source()))
        board = result.document.one('/Board')
        signal = result.classes[1]
        signal['Name'] = 'Changed class'
        signal['FixedLength'] = Decimal('12.5')
        row = signal.one('LengthResults/Rules/Rule')
        row['Length'] = Decimal('6.25')
        projected = project_rules(board)
        policy = projected.one('LengthRules/LengthRule')
        self.assertEqual(policy.values, ('Changed class', Decimal('12.5'), Decimal('.4'), 'Y', 'Y', 1, 1))
        self.assertEqual(projected.one('MainLengthRule/pt').values, (0, 0, 1, 0, 2, Decimal('3.5'), 'N'))
        self.assertEqual(policy.one('pt').values, (0, 0, 2, 0, 1, Decimal('6.25'), 'Y'))
        imported = assemble_rules(current_input(board, projected)).document.one('/Board')
        self.assertEqual(signature(imported), signature(board))
        self.assertEqual(text(project_rules(imported)), text(projected))

    def test_active_class_without_results_still_has_a_generated_policy(self):
        result = assemble_rules(prepare_core(fixture()))
        board = result.document.one('/Board')
        result.classes[1]['CheckLength'] = True
        policy = project_rules(board).one('LengthRules/LengthRule')
        self.assertEqual(policy.values, ('Signal', -1, Decimal('7.62'), 'N', 'N', 1, 1))
        self.assertEqual(policy.children(), [])
        self.assertIsNone(result.classes[1].child('LengthResults'))

    def test_literal_exclamation_spelling_warns_without_changing_the_current_name(self):
        result = assemble_rules(prepare_core(fixture()))
        board = result.document.one('/Board')
        result.layers[0]['Name'] = 'Top!side'
        report = ConversionReport()
        projected = project_rules(board, report=report)
        self.assertEqual([notice.rule for notice in report.warnings], ['layer-name-spelling'])
        self.assertEqual(result.layers[0]['Name'], 'Top!side')
        imported = assemble_rules(current_input(board, projected)).document.one('/Board')
        self.assertEqual(imported.one('Layers/Layer[1]')['Name'], 'Top side')

    def test_absent_matrix_overrides_are_generated_as_inherited_without_editing_the_model(self):
        result = assemble_rules(prepare_core(fixture()))
        board = result.document.one('/Board')
        result.document.remove(board.one('ClassClearances/Cell[1]'))
        matrix = project_rules(board).one('CTC_Cells')
        self.assertEqual(matrix.one('Cell[1]').values, (0, 0, 'Y'))
        self.assertEqual(matrix.one('Cell[1]/pt').values, (-1,))
        self.assertEqual(len(board.one('ClassClearances').children()), 2)
        for cell in tuple(board.one('ClassClearances').children()):
            result.document.remove(cell)
        self.assertEqual(project_rules(board).one('CTC_Cells').values, (0,))

    def test_unknown_content_missing_layer_rows_and_stored_indices_are_errors(self):
        for problem in ('unknown', 'missing layer', 'stored index'):
            with self.subTest(problem=problem):
                result = assemble_rules(prepare_core(fixture()))
                board = result.document.one('/Board')
                if problem == 'unknown':
                    result.layers[0].add('Unmapped', 1)
                elif problem == 'missing layer':
                    result.document.remove(result.classes[1].one('LayProperties/LayProperty[1]'))
                else:
                    result.layers[0].add('NetNumber', 0)
                before = dumps(result.document, preserve=False)
                with self.assertRaises(PcbError):
                    project_rules(board)
                self.assertEqual(dumps(result.document, preserve=False), before)


if __name__ == '__main__':
    unittest.main()
