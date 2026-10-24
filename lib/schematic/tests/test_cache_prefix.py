"""Active cache prefixes use current member positions, without count snapshots."""
import unittest

from lib import ReferenceError
from lib.tests.test_cached_properties import sample


def design():
    doc, _ = sample()
    schematic = doc.one('/Schematic')
    slots = schematic.one('CacheLib/Slots')
    first = slots.children('Slot')[0]
    second = slots.append(first.clone())
    links = schematic.one('DesignCache_Links')
    a, b = links.add('Link', 0), links.add('Link', 1)
    schematic['DesignCache_Count'] = 0
    return doc, schematic, (a, b), (first, second)


class CachePrefixTests(unittest.TestCase):
    def test_expansion_activates_new_links_and_preserves_existing_identities(self):
        doc, schematic, (a, b), (first, second) = design()
        schematic['DesignCache_Count'] = 1
        links = doc.references.outgoing(schematic, role='design-cache-slot')
        self.assertEqual({link.target for link in links}, {first, second})
        second.move_to(first.parent, 0)
        self.assertEqual((a['SlotIndex'], b['SlotIndex']), (1, 0))
        doc.validate()
        cloned = doc.clone()
        cloned.one('/Schematic/CacheLib/Slots/Slot[1]').move_to(cloned.one('/Schematic/CacheLib/Slots'), 1)
        self.assertEqual([link['SlotIndex'] for link in cloned.select('/Schematic/DesignCache_Links/Link')], [0, 1])
        self.assertEqual((a['SlotIndex'], b['SlotIndex']), (1, 0))
        cloned.validate()

    def test_shrink_requires_explicit_discard_of_links_leaving_the_active_prefix(self):
        doc, schematic, (_, b), _ = design()
        schematic['DesignCache_Count'] = 1
        reference = next(link for link in doc.references.outgoing(schematic, role='design-cache-slot')
                         if link.indices[0].field is b)
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            schematic['DesignCache_Count'] = 0
        self.assertEqual(schematic['DesignCache_Count'], 1)
        doc.references.discard(reference)
        schematic['DesignCache_Count'] = 0
        self.assertEqual(b['SlotIndex'], 1)
        doc.validate()

    def test_active_member_cannot_move_to_an_inactive_position(self):
        doc, schematic, (a, b), _ = design()
        before = a.parent.children()
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            a.move_to(a.parent, 1)
        self.assertEqual(a.parent.children(), before)
        self.assertEqual(schematic['DesignCache_Count'], 0)
        doc.validate()

    def test_new_unknown_link_keeps_its_scope_and_guard_in_a_clone(self):
        doc, schematic, (_, b), _ = design()
        b['SlotIndex'] = 99
        schematic['DesignCache_Count'] = 1
        issue = next(item for item in doc.references.issues if any(index.field is b for index in item.indices))
        self.assertEqual(issue.collections, (schematic.one('CacheLib/Slots'),))
        clone = doc.clone()
        with self.assertRaisesRegex(ReferenceError, 'reference mode'):
            clone.one('/Schematic')['DesignCache_Count'] = 0
        clone.references.discard_issue(clone.references.issues[-1])
        clone.one('/Schematic')['DesignCache_Count'] = 0
        self.assertEqual(schematic['DesignCache_Count'], 1)
        clone.validate()
        doc.validate()
