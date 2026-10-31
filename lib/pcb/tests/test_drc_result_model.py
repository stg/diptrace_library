"""Saved checks follow design identities without recalculating their values."""
from decimal import Decimal
import unittest
from unittest.mock import patch

from lib.common.conversion import ConversionReport, import_diagnostics
from lib.common.references import Property, ReferenceError
from lib.pcb.formats.assembly.graphics import assemble_graphics
from lib.pcb.model import drc_results
from lib.pcb.tests.test_graphics import design


def source():
    data, _, _ = design()
    errors = data.board.add('DesignErrors')
    row = errors.add('DesignError', 17)
    for name, value in dict(Enabled=True, X=1, Y=2, Value=Decimal('.1'), Rule=Decimal('.2'),
            Type=0, RuleType=0, RuleLay=1, ObjectType1=4, Object1=41, SubObject1=5,
            Point1=-1, ExtObject1=-1, ObjectType2=7, Object2=500, SubObject2=-1,
            Point2=-1, ExtObject2=-1).items():
        row.add(name, value)
    mask = row.add('Lays')
    for flag in (False, True, False, False, False, False, False, False):
        mask.add('Item', flag)
    return data


class DrcResultModelTests(unittest.TestCase):
    def test_saved_selectors_bind_current_objects_and_only_affected_layers(self):
        result = assemble_graphics(source())
        document = result.document
        row = document.one('/Board/DesignErrors/DesignError')
        self.assertIs(row.schema, drc_results.ERROR)
        self.assertEqual(row.values, ())
        self.assertEqual(row['Id'], 0)
        self.assertIs(row['Target1'], result.rules.routing.core.pads[41, 5])
        self.assertIs(row['Target2'], result.pours[500])
        self.assertEqual((row['Object1'], row['SubObject1'], row['Object2']), (0, 0, 0))
        for name in ('Object1', 'SubObject1', 'Object2', 'Point1', 'ExtObject1', 'RuleLay', 'ObjectNetClass1'):
            self.assertIsNone(row.child(name))
        self.assertIs(row['RuleLayer'], result.rules.layers[1])
        self.assertIsNone(row.child('Lays'))
        layer = row.one('Layers/Layer')
        self.assertIs(layer['Layer'], result.rules.layers[1])
        self.assertEqual(layer['Index'], 1)
        self.assertIsNone(layer.child('Index'))
        document.references.validate()

    def test_data_edits_reorder_and_pad_moves_preserve_snapshot_and_identity(self):
        result = assemble_graphics(source())
        document = result.document
        row = document.one('/Board/DesignErrors/DesignError')
        pad = row['Target1']
        second = document.copy(result.rules.routing.core.components[41], fields={'RefDes': 'U2'})
        observed = document.root.add('Observed', -1)
        document.references.bind(observed, row, Property(observed, 'Object1'))
        with patch.object(document.root, 'walk', side_effect=AssertionError('global tree scan')), \
                patch.object(type(document.references), '__iter__', side_effect=AssertionError('global graph scan')):
            pad.move_to(second.one('Pattern/Pads'), 1)
            result.rules.layers[1].move_to(result.rules.layers[1].parent, 0)
            pad['X'] = 100
            row['Rule'] = Decimal('.3')
            self.assertEqual((row['Object1'], row['SubObject1']), (1, 1))
            self.assertEqual(observed.values, (1,))
            self.assertEqual(row.one('Layers/Layer')['Index'], 0)
            self.assertEqual(row['RuleLay'], 0)
            self.assertEqual((row['X'], row['Y'], row['Value']), (1, 2, Decimal('.1')))
        document.references.validate()

    def test_retarget_guards_copy_clone_and_removal_are_atomic(self):
        result = assemble_graphics(source())
        document = result.document
        row = document.one('/Board/DesignErrors/DesignError')
        reference, = document.references.outgoing(row, role=drc_results.OBJECT_ROLES[0])
        other = result.rules.routing.core.pads[41, 12]
        row['Target1'] = other
        self.assertIs(row['Target1'], other)
        with self.assertRaises(ReferenceError):
            row['ObjectType1'] = 7
        self.assertEqual(row['ObjectType1'], 4)
        with self.assertRaises(ReferenceError):
            document.references.retarget(reference, result.pours[500])
        with self.assertRaises(ReferenceError):
            document.remove(other)
        clone = document.clone()
        copied = clone.one('/Board/DesignErrors/DesignError')
        self.assertIsNot(copied['Target1'], other)
        self.assertIs(copied['Target1']._owner(), clone)
        duplicate = document.copy(row)
        self.assertIs(duplicate['Target1'], other)
        document.remove(duplicate)
        with self.assertRaises(ReferenceError):
            row.move_to(document.one('/Board/Nets'))
        document.references.validate()
        clone.references.validate()

    def test_unavailable_targets_and_layers_can_be_repaired_or_cleared_explicitly(self):
        data = source()
        data.board.one('DesignErrors/DesignError/Object2').set_values(999)
        data.board.one('DesignErrors/DesignError/RuleLay').set_values(99)
        @import_diagnostics('dip')
        def read(data):
            return assemble_graphics(data).document
        report = ConversionReport()
        document = read(data, report=report)
        row = document.one('/Board/DesignErrors/DesignError')
        self.assertEqual(row['Object2'], 999)
        self.assertIsNotNone(row.child('UnresolvedTarget2'))
        with self.assertRaises(ReferenceError):
            row['Target2']
        with self.assertRaises(ReferenceError):
            row['RuleLayer']
        row['Target2'] = document.one('/Board/CopperPours/CopperPour')
        row['RuleLayer'] = document.one('/Board/Layers/Layer[1]')
        self.assertIsNone(row.child('UnresolvedTarget2'))
        self.assertIsNone(row.child('UnresolvedRuleLay'))
        self.assertEqual((row['Object2'], row['RuleLay']), (0, 0))
        self.assertFalse(document.references.issues)
        self.assertTrue(report.warnings)
        row['Target1'] = None
        self.assertEqual((row['Object1'], row['SubObject1'], row['Point1'], row['ExtObject1']), (-1, -1, -1, -1))
        document.references.validate()

    def test_unavailable_component_objects_detach_but_keep_the_result(self):
        @import_diagnostics('dip')
        def read(data):
            return assemble_graphics(data).document
        data = source()
        data.board.one('DesignErrors/DesignError/SubObject1').set_values(99)
        report = ConversionReport()
        document = read(data, report=report)
        row = document.one('/Board/DesignErrors/DesignError')
        self.assertIsNone(row['Target1'])
        self.assertEqual((row['Object1'], row['SubObject1'], row['Point1']), (-1, -1, -1))
        self.assertEqual(row['Value'], Decimal('.1'))
        self.assertTrue(any(n.rule == 'stale-design-error-targets' for n in report.infos))
        document.references.validate()

    def test_layer_duplicates_and_target_disable_fail_without_partial_changes(self):
        result = assemble_graphics(source())
        document = result.document
        row = document.one('/Board/DesignErrors/DesignError')
        with self.assertRaises(ReferenceError):
            row['Target2']['Enabled'] = False
        self.assertTrue(row['Target2']['Enabled'])
        layer = row.one('Layers/Layer')
        with self.assertRaises(ReferenceError):
            document.copy(layer)
        self.assertEqual(row.one('Layers').children(), [layer])
        document.references.validate()

    def test_whole_outline_is_distinct_from_an_outline_vertex(self):
        data = source()
        row = data.board.one('DesignErrors/DesignError')
        row.one('ObjectType2').set_values(1)
        row.one('Object2').set_values(-1)
        result = assemble_graphics(data)
        self.assertIs(result.document.one('/Board/DesignErrors/DesignError')['Target2'], result.document.one('/Board'))
        result.document.references.validate()

    def test_component_qualified_drawings_keep_the_component_without_a_false_primitive_identity(self):
        @import_diagnostics('dip')
        def read(data):
            return assemble_graphics(data).document
        data = source()
        row = data.board.one('DesignErrors/DesignError')
        row.one('ObjectType2').set_values(2)
        row.one('Object2').set_values(100)
        row.one('ExtObject2').set_values(0)
        report = ConversionReport()
        document = read(data, report=report)
        row = document.one('/Board/DesignErrors/DesignError')
        component = document.one('/Board/Components/Component')
        self.assertIs(row['Target2'], component)
        self.assertEqual((row['Object2'], row['SubObject2'], row['Point2'], row['ExtObject2']), (-1, -1, -1, 0))
        self.assertIsNone(row.child('Object2'))
        self.assertTrue(any(n.rule == 'design-error-drawing-detail' for n in report.infos))
        second = document.copy(component, fields={'RefDes': 'U2'})
        row['Target2'] = second
        self.assertEqual(row['ExtObject2'], 1)
        second.move_to(second.parent, 0)
        self.assertEqual(row['ExtObject2'], 0)
        document.clone().references.validate()
        document.references.validate()


if __name__ == '__main__':
    unittest.main()
