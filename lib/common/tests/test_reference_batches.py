"""Atomic planning of several related links handles their collective graph."""
import unittest

from lib import Document, Guard, Index, Property, ReferenceError


class ReferenceBatchTests(unittest.TestCase):
    def chain(self):
        doc = Document()
        first, middle, last = [doc.root.add('Item', name) for name in ('master', 'old', 'old')]
        specs = ((last, middle, 'last', (Property(last),), ()),
                 (middle, first, 'middle', (Property(middle),), ()))
        return doc, first, middle, last, specs

    def test_batch_settles_property_chains_independent_of_addition_order(self):
        doc, first, middle, last, specs = self.chain()
        prepared = doc.references._prepare_additions(specs)
        self.assertEqual((middle.values, last.values, len(doc.references)), (('old',), ('old',), 0))
        doc.references._apply_additions(prepared)
        self.assertEqual((middle.values, last.values), (('master',), ('master',)))
        first.set_values('renamed')
        doc.rebuild(force=False)
        self.assertEqual((middle.values, last.values), (('renamed',), ('renamed',)))
        doc.validate()

    def test_collective_cycle_fails_before_registering_any_link(self):
        doc, first, middle, _, _ = self.chain()
        specs = ((first, middle, 'forward', (Property(first),), ()),
                 (middle, first, 'backward', (Property(middle),), ()))
        with self.assertRaisesRegex(ReferenceError, 'cycle'):
            doc.references._prepare_additions(specs)
        self.assertEqual(len(doc.references), 0)
        self.assertEqual((first.values, middle.values), (('master',), ('old',)))

    def test_downstream_guard_rejects_the_entire_proposed_batch(self):
        doc, first, middle, last, specs = self.chain()
        slot = last.add('Target', 0)
        guard = doc.references.bind(last, first, Index(slot), guards=(Guard(last, ('old',)),))
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            doc.references._prepare_additions(specs)
        self.assertEqual(tuple(doc.references), (guard,))
        self.assertEqual((middle.values, last.values), (('old',), ('old',)))
        doc.validate()
