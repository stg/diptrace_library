"""Destination omissions preserve immutable facts, ordering and occurrences."""
import unittest
from unittest.mock import patch

from lib.common.model import Value
from lib.common.xml_plan import XmlBuilder, XmlPlan
from lib.common.xml_projection import XmlPlanEdits


class XmlPlanEditTests(unittest.TestCase):
    def test_omissions_rebuild_only_changed_branches_without_editable_materialization(self):
        builder = XmlBuilder('Source')
        builder.attribute('Type', 'Test')
        data = builder.add('Data')
        data.attribute('Flag', False)
        data.add('Text', 'authored')
        data.add('Number', 0)
        untouched = builder.add('Other')
        untouched.add('Null', None)
        original = builder.freeze()
        with patch.object(XmlPlan, 'element', side_effect=AssertionError('editable materialization')):
            with XmlPlanEdits(original) as output:
                node = output.root.one('Data')
                output.omit(node, 'Flag')
                output.omit(node, 'Text')
                changed = output.finish()
        self.assertEqual(tuple(child.kind for child in changed.child('Data').children), ('Number',))
        self.assertEqual(changed.child('Data').child('Number').arguments, (Value.of(0),))
        self.assertIs(changed.child('Other'), original.child('Other'))
        self.assertEqual(original.child('Data').attribute('Flag'), False)
        self.assertIsNotNone(original.child('Data').child('Text'))
        self.assertEqual(changed.attributes, original.attributes)

    def test_equal_shared_plans_are_independent_output_occurrences(self):
        shared = XmlPlan('Item', attributes=(('Flag', Value.of(True)),))
        original = XmlPlan('Source', children=(shared, shared))
        with XmlPlanEdits(original) as output:
            first, second = output.root.children('Item')
            self.assertNotEqual(first.path, second.path)
            output.omit(first, 'Flag')
            changed = output.finish()
        self.assertEqual(changed.children[0].attributes, ())
        self.assertIs(changed.children[1], shared)
        self.assertEqual(shared.attribute('Flag'), True)

    def test_empty_and_absent_omissions_return_the_original_plan(self):
        original = XmlPlan('Source', children=(XmlPlan('Data'),))
        with XmlPlanEdits(original) as output:
            output.omit(output.root, 'Missing')
            self.assertIs(output.finish(), original)

    def test_duplicate_fields_and_foreign_handles_cannot_hide_invalid_output(self):
        original = XmlPlan('Source', attributes=(('Flag', Value.of(1)),), children=(XmlPlan('Flag'),))
        with XmlPlanEdits(original) as output, XmlPlanEdits(XmlPlan('Other')) as foreign:
            with self.assertRaisesRegex(ValueError, 'one generated XML field'):
                output.omit(output.root, 'Flag')
            with self.assertRaisesRegex(ValueError, 'this XML projection'):
                output.omit(foreign.root, 'Flag')
            self.assertIs(output.finish(), original)

    def test_detached_diagnostics_keep_the_same_paths_as_standalone_syntax(self):
        original = XmlPlan('Library', children=(XmlPlan('Part', attributes=(('Size', Value.of(3)),)),))
        with XmlPlanEdits(original, detached=True) as detached:
            self.assertEqual(detached.root.one('Part').one('Size').path, '/Part[1]/Size[1]')
        with XmlPlanEdits(original) as document:
            self.assertEqual(document.root.one('Part').one('Size').path, '/Library[1]/Part[1]/Size[1]')

    def test_element_walk_avoids_attribute_handles_but_preserves_ordinals(self):
        plan = XmlPlan('Source', attributes=(('Item', Value.of(1)),), children=(XmlPlan('Item'),))
        with XmlPlanEdits(plan) as output:
            nodes = list(output.root.walk_elements(include_self=True))
            self.assertEqual([node.path for node in nodes], ['/Source[1]', '/Source[1]/Item[2]'])
            self.assertNotIn(0, output.root._handles)


if __name__ == '__main__':
    unittest.main()
