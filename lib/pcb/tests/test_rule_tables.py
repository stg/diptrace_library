"""Rule tables keep their meaning when layers, styles and classes are edited."""
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib.common.references import Property, ReferenceError
from lib.pcb.formats.assembly.board_rules import assemble_rules
from lib.pcb.tests.test_core_assembly import fixture


def design(*, routing_defaults=False, matrix_size=2):
    decoded = fixture()
    decoded.upgrades = SimpleNamespace(nets=(), separate_traces=())
    board = decoded.board
    for index in range(2):
        layer = board.child('Layers') or board.add('Layers')
        item = layer.add('Layer', ('Top', 'Bottom')[index])
        item.add('Number', 20+index)
        item.add('Type', 0)
    styles = board.add('ViaStyles')
    styles.add('ViaStyle', 'Large', True, 2, 1, 0, 1)
    styles.add('ViaStyle', 'Small', True, 1, Decimal('.5'), 0, 1)
    classes = board.add('NetClasses')
    for index, name in enumerate(('Default', 'Power')):
        net_class = classes.add('NetClass', name)
        net_class.add('AllLayers', index == 0)
        rows = net_class.add('LayProperties')
        for layer in range(2):
            rule = rows.add('LayProperty')
            rule.add('Width', 10*index+layer+1)
            details = rule.add('ClearDetails')
            for first in range(4):
                details.add('pt', *(Decimal(first*10+second)/100 for second in range(5)))
        net_class.add('AllowedVias').add('ViaStyle', 1)
        flags = net_class.add('RouteLayers')
        flags.add('Item', True)
        flags.add('Item', False)
    board.add('ClassToClass', True)
    matrix = board.add('ClassClearances')
    for first in range(matrix_size):
        row = matrix.add('Row')
        for second in range(matrix_size):
            cell = row.add('Cell')
            cell.add('AllLayers', first == second)
            values = cell.add('Values')
            for value in ((Decimal('.6'), Decimal('.9')) if first != second else (-1,)):
                values.add('Item', value)
    for index, kind in enumerate(('DRC', 'LastDRC')):
        drc = board.add(kind)
        drc.add('AllLayers', index == 1)
        clearances, sizes = drc.add('LayClearances'), drc.add('LaySizes')
        for layer in range(2):
            clearances.add('LayClearance', layer).add('ClearanceDetails').add('TraceToVia', layer+1)
            sizes.add('LaySize', layer).add('MinTrace', layer+2)
    if routing_defaults:
        routing = board.add('Settings').add('Routing')
        routing.add('TraceWidth', Decimal('.6'))
        routing.add('TraceClearance', Decimal('.9'))
        differential = classes.children()[1]
        differential.add('Type', 1)
        for row in differential.select('LayProperties/LayProperty'):
            row.one('Width').set_values(-1)
            row.add('Clearance', -1)
            row.add('DifClearance', -1)
    return assemble_rules(decoded)


class RuleTableTests(unittest.TestCase):
    def test_surplus_matrix_storage_does_not_create_rules_for_nonexistent_classes(self):
        from lib.common.conversion import ConversionReport, import_diagnostics
        @import_diagnostics('dip')
        def imported():
            return design(matrix_size=5).document
        report = ConversionReport()
        document = imported(report=report)
        cells = document.select('/Board/ClassClearances/Cell')
        classes = document.select('/Board/NetClasses/NetClass')
        self.assertEqual(len(cells), 3)
        self.assertEqual([(cell['Class1'], cell['Class2']) for cell in cells],
                         [(classes[0], classes[0]), (classes[1], classes[0]), (classes[1], classes[1])])
        self.assertEqual([row['Clearance'] for row in cells[1].select('LayerClearances/LayerClearance')],
                         [Decimal('.6'), Decimal('.9')])
        self.assertIn('class-clearance-table-normalization', {n.rule for n in report.infos})
        classes[0].move_to(classes[0].parent)
        self.assertIs(cells[1]['Class1'], classes[1])
        document.references.validate()

    def test_negative_matrix_coordinates_remain_invalid(self):
        from lib.common.model import Element
        from lib.pcb.formats.assembly.rule_tables import _matrix_cells
        matrix = Element('ClassClearances')
        matrix.add('Cell', -1, 0)
        with self.assertRaisesRegex(ValueError, 'invalid class clearance coordinates'):
            list(_matrix_cells(matrix))

    def test_import_normalizes_uniform_rows_and_binds_specific_layer_identities(self):
        result = design()
        board = result.document.one('/Board')
        uniform, specific = board.select('NetClasses/NetClass')
        self.assertEqual(len(uniform.select('LayProperties/LayProperty')), 1)
        self.assertIsNone(uniform.one('LayProperties/LayProperty')['Layer'])
        self.assertEqual(uniform.one('LayProperties/LayProperty')['Width'], 1)
        properties = specific.select('LayProperties/LayProperty')
        self.assertEqual([row['Layer'] for row in properties], list(result.layers.values()))
        self.assertEqual([row['LayerName'] for row in properties], ['Top', 'Bottom'])
        details = properties[0].one('ClearanceDetails')
        self.assertEqual(len(details.children()), 14)
        self.assertEqual(details['ViaToPad'], Decimal('.12'))
        self.assertIsNone(properties[0].child('ClearDetails'))
        self.assertIs(uniform.one('AllowedVias/ViaStyle')['Via'], result.via_styles[1])
        self.assertEqual([flag['Enabled'] for flag in uniform.select('RouteLayers/Item')], [True, False])
        self.assertEqual([flag['Layer'] for flag in uniform.select('RouteLayers/Item')], list(result.layers.values()))
        self.assertEqual([row['Layer'] for row in board.select('DRC/LaySizes/LaySize')], list(result.layers.values()))
        self.assertEqual(len(board.select('LastDRC/LaySizes/LaySize')), 1)
        self.assertIsNone(board.one('LastDRC/LaySizes/LaySize')['Layer'])
        self.assertFalse(board.one('DRC/LaySizes/LaySize[1]').values)

    def test_symmetric_matrix_becomes_one_rule_per_unordered_class_pair(self):
        result = design()
        cells = result.document.select('/Board/ClassClearances/Cell')
        self.assertEqual(len(cells), 3)
        self.assertEqual([(cell['NetClass1'], cell['NetClass2']) for cell in cells], [(0, 0), (1, 0), (1, 1)])
        self.assertIsNone(cells[0]['Clearance'])
        self.assertFalse(cells[1]['AllLayers'])
        rows = cells[1].select('LayerClearances/LayerClearance')
        self.assertEqual([row['Layer'] for row in rows], list(result.layers.values()))
        self.assertEqual([row['Clearance'] for row in rows], [Decimal('.6'), Decimal('.9')])
        self.assertIsNone(cells[1].child('Values'))
        self.assertIsNone(result.document.one('/Board/ClassClearances').child('Row'))

    def test_reordering_and_renaming_keep_rule_targets_and_copies_current(self):
        result = design()
        document = result.document
        specific = result.classes[1].one('LayProperties/LayProperty[1]')
        via = result.classes[0].one('AllowedVias/ViaStyle')
        cell = document.one('/Board/ClassClearances/Cell[2]')
        probe = document.root.add('Probe', 0, '', 0, 0)
        document.references.bind(probe, specific, Property(probe, 'Lay'), Property(probe, 'LayerName', argument=1), role='layer-copy')
        document.references.bind(probe, via, Property(probe, 'Id', argument=2), role='via-copy')
        document.references.bind(probe, cell, Property(probe, 'NetClass1', argument=3), role='class-copy')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            result.layers[0].move_to(result.layers[0].parent, 1)
            result.layers[0]['Name'] = 'Renamed'
            result.via_styles[1].move_to(result.via_styles[1].parent, 0)
            result.classes[1].move_to(result.classes[1].parent, 0)
            self.assertEqual(probe.values, (1, 'Renamed', 0, 0))
        self.assertIs(specific['Layer'], result.layers[0])
        self.assertEqual([row['Lay'] for row in cell.select('LayerClearances/LayerClearance')], [1, 0])

    def test_duplicate_unordered_class_pair_is_rejected_before_retargeting(self):
        result = design()
        cell = result.document.one('/Board/ClassClearances/Cell[1]')
        with self.assertRaisesRegex(ReferenceError, 'unordered class pair'):
            cell['Class1'] = result.classes[1]
        self.assertIs(cell['Class1'], result.classes[0])
        self.assertEqual((cell['NetClass1'], cell['NetClass2']), (0, 0))

    def test_referenced_rules_prevent_removing_layers_styles_and_classes(self):
        result = design()
        for target in (result.layers[0], result.via_styles[1], result.classes[1]):
            with self.subTest(kind=target.kind), self.assertRaises(ReferenceError):
                result.document.remove(target)
            self.assertIsNotNone(target.parent)

    def test_duplicate_layer_rules_fail_atomically(self):
        result = design()
        rules = result.classes[1].select('LayProperties/LayProperty')
        with self.assertRaisesRegex(ReferenceError, 'already has this target'):
            rules[1]['Layer'] = result.layers[0]
        self.assertIs(rules[1]['Layer'], result.layers[1])
        self.assertEqual([row['Lay'] for row in rules], [0, 1])

    def test_copying_a_class_pair_requires_a_distinct_pair(self):
        result = design()
        collection = result.document.one('/Board/ClassClearances')
        original = collection.children()[1]
        before = collection.children()
        with self.assertRaisesRegex(ReferenceError, 'unordered class pair'):
            result.document.copy(original, parent=collection)
        self.assertEqual(collection.children(), before)

    def test_clone_remaps_rule_targets(self):
        result = design()
        duplicate = result.document.clone()
        board = duplicate.one('/Board')
        cell = board.one('ClassClearances/Cell[2]')
        self.assertIs(cell['Class1'], board.one('NetClasses/NetClass[2]'))
        self.assertIs(cell.one('LayerClearances/LayerClearance[1]')['Layer'], board.one('Layers/Layer[1]'))
        self.assertIs(board.one('NetClasses/NetClass[1]/AllowedVias/ViaStyle')['Via'], board.one('ViaStyles/ViaStyle[2]'))
        self.assertIsNot(cell['Class1'], result.classes[1])

    def test_routing_defaults_share_values_with_the_default_class(self):
        result = design(routing_defaults=True)
        document = result.document
        board = document.one('/Board')
        routing = board.one('Settings/Routing')
        default = result.classes[0].one('LayProperties/LayProperty')
        self.assertIs(board['DefaultClass'], result.classes[0])
        self.assertEqual((default['Width'], default['Clearance']), (Decimal('.6'), Decimal('.9')))
        self.assertIsNone(routing.child('TraceWidth'))
        self.assertIsNone(routing.child('TraceClearance'))
        for row in result.classes[1].select('LayProperties/LayProperty'):
            self.assertEqual((row['Width'], row['Clearance'], row['DifClearance']),
                             (Decimal('.6'), Decimal('.9'), Decimal('.9')))
        probe = document.root.add('Probe', 0)
        document.references.bind(probe, routing, Property(probe, 'TraceWidth'), role='routing-copy')
        with patch.object(document.root, 'walk', side_effect=AssertionError('whole document scan')), \
             patch.object(type(document.references), '__iter__', side_effect=AssertionError('whole graph scan')):
            default['Width'] = 5
            self.assertEqual((routing['TraceWidth'], probe.values), (5, (5,)))
            routing['TraceWidth'] = 7
            self.assertEqual((default['Width'], probe.values), (7, (7,)))
            # Reordering does not change which class supplies the defaults.
            result.classes[1].move_to(result.classes[1].parent, 0)
            self.assertIs(board['DefaultClass'], result.classes[0])
            self.assertEqual(routing['TraceWidth'], 7)
            board['DefaultClass'] = result.classes[1]
            self.assertEqual(probe.values, (Decimal('.6'),))
            result.classes[1].one('LayProperties/LayProperty[1]')['Width'] = 9
            self.assertEqual(probe.values, (9,))
            default['Width'] = 11
            self.assertEqual(probe.values, (9,))

    def test_cloned_routing_aliases_use_the_cloned_default_class(self):
        result = design(routing_defaults=True)
        duplicate = result.document.clone()
        board = duplicate.one('/Board')
        self.assertIs(board['DefaultClass'], board.one('NetClasses/NetClass[1]'))
        board.one('Settings/Routing')['TraceClearance'] = 4
        self.assertEqual(board.one('NetClasses/NetClass[1]/LayProperties/LayProperty')['Clearance'], 4)
        self.assertEqual(result.document.one('/Board/Settings/Routing')['TraceClearance'], Decimal('.9'))


if __name__ == '__main__':
    unittest.main()
