"""Nested atomic plans retain their enclosing prospective tree and order."""
import unittest

from lib.common.model import Element
from lib.common.structural_edits import preview_structure


class StructuralPreviewTests(unittest.TestCase):
    def test_nested_preview_composes_then_restores_both_structural_domains(self):
        outer, inner = Element('Outer'), Element('Inner')
        a, b = outer.add('Item'), inner.add('Item')
        added_outer, added_inner = Element('Item'), Element('Item')
        with preview_structure({outer: (added_outer, a)}, {added_outer: outer}, {a: 1}):
            with preview_structure({inner: (added_inner, b)}, {added_inner: inner}, {b: 1}):
                self.assertEqual(outer.children(), [added_outer, a])
                self.assertIs(added_outer.parent, outer)
                self.assertEqual(a._ordinal(), 1)
                self.assertEqual(inner.children(), [added_inner, b])
                self.assertIs(added_inner.parent, inner)
                self.assertEqual(b._ordinal(), 1)
            self.assertEqual(outer.children(), [added_outer, a])
            self.assertEqual(inner.children(), [b])
            self.assertIsNone(added_inner.parent)
        self.assertEqual(outer.children(), [a])
        self.assertIsNone(added_outer.parent)
        self.assertEqual(a._ordinal(), 0)


if __name__ == '__main__':
    unittest.main()
