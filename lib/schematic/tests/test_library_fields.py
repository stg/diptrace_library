"""Library facts have named access; bookkeeping positions follow current order."""
import unittest

from lib import Element, parse, serialize
from lib.tests.test_cached_properties import sample
from lib.schematic.model.refs import bind_schematic_references


class LibraryFieldTests(unittest.TestCase):
    def test_hole_editing_crosses_all_formats_without_positional_storage(self):
        doc, _ = sample()
        pattern = doc.one('//Definition/Pattern')
        hole = pattern.one('Holes').insert(Element('Hole', True, False, 3, 6, 4, 2, -1), 1)
        bind_schematic_references(doc)
        hole['X'] = 12
        hole['HoleDiam'] = 1.5
        self.assertTrue(all(isinstance(item, Element) for item in hole.items))
        self.assertEqual(hole.schema.field('HoleDiam').unit, 'shared length')
        for format in ('dch', 'asc', 'dchxml'):
            with self.subTest(format=format):
                loaded = parse(serialize(doc, format=format), format=format)
                current = loaded.one('//Definition/Pattern/Holes/Hole[Enabled=true]')
                loaded_pattern = current.parent.parent
                self.assertEqual(current['X']-loaded_pattern['OriginX'], hole['X']-pattern['OriginX'])
                self.assertEqual(current['HoleDiam'], 1.5)
        with self.assertRaises(TypeError):
            hole['Locked'] = 0
        self.assertFalse(hole['Locked'])

    def test_slot_and_variant_positions_derive_from_current_order(self):
        doc, _ = sample()
        slots = doc.one('/Schematic/CacheLib/Slots')
        first = slots.one('Slot')
        second = slots.append(first.clone())
        bind_schematic_references(doc)
        first['LibPath'] = 'library.eli'
        first.move_to(slots, 1)
        self.assertEqual(first['Index'], 1)
        self.assertEqual(second['Index'], 0)
        self.assertEqual(first['LibPath'], 'library.eli')
        self.assertIsNone(first.child('Index'))
        self.assertFalse(any(link.role == 'cache-slot-order' for link in doc.references))
        variants = first.children('Definition')
        other = first.append(variants[0].clone())
        other.move_to(first, 0)
        self.assertEqual(other['Index'], 0)
        self.assertEqual(variants[0]['Index'], 1)
        with self.assertRaises(TypeError):
            first['Index'] = 2

    def test_verification_vector_has_a_type_and_fixed_arity_without_invented_names(self):
        doc, part = sample()
        flags = (True, False, True, False, True, False, True)
        part['Verification'] = flags
        definition = part.schema.field('Verification')
        self.assertEqual(definition.item_kind, 'boolean')
        self.assertEqual(definition.length, 7)
        for invalid in (flags[:-1], flags+(False,), (1, *flags[1:])):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                part['Verification'] = invalid
            self.assertEqual(part['Verification'], flags)
        loaded = parse(serialize(doc, format='dch'), format='dch')
        self.assertEqual(loaded.one('//Definition/Part')['Verification'], flags)
