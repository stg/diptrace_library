"""Current collection rows own meaning; file counts are generated projections."""
import unittest

from lib import ConversionReport, Element, new_schematic, parse, parse_source, serialize
from lib.schematic.model.refs import bind_schematic_references
from lib.tests.test_cached_properties import sample
from lib.schematic.model.pads import empty_pad


class CollectionSchemaTests(unittest.TestCase):
    def test_pad_construction_uses_named_fields_without_segment_counts(self):
        pad = empty_pad(0)
        pad['StringNumber'] = 'A'
        self.assertEqual(pad['StringNumber'], 'A')
        for name in ('PadMask_TopSegments', 'PadMask_BotSegments'):
            self.assertEqual(pad.child(name).arguments, ())

    def test_named_collections_have_no_stored_header_count(self):
        doc, _ = sample()
        for owner in doc.root.walk():
            if owner.schema is not None and owner.schema.name in (
                    'Classifications', 'PossibleNames', 'PasteSegments', 'ProjectFolders',
                    'ProjectLibraries', 'DesignCacheLinks'):
                self.assertEqual(owner.arguments, ())
                self.assertFalse(owner.schema.fields)
                self.assertTrue(owner.schema.children)
        with self.assertRaises(TypeError):
            doc.one('//Definition/Pattern')['PossibleNames']

    def test_additions_project_current_counts_across_each_format(self):
        doc, part = sample()
        pattern = doc.one('//Definition/Pattern')
        pattern.one('PossibleNames').add('PossibleName', 'Alternate')
        part.one('Component_CategoryTypes').add('CategoryType', 'Type', 'Subtype', 5, 6)
        folder = doc.one('/Schematic/ProjectLibs_Folders').add('Folder', 'components')
        folder.add('VariablePath', 'components')
        bind_schematic_references(doc)
        raw = parse_source(serialize(doc, format='asc', report=ConversionReport()), format='asc')
        self.assertEqual(raw.one('/Schematic/ProjectLibs_Folders').values, (1,))
        self.assertEqual(raw.one('//cl_PossibleNames').values, (1,))
        for first in ('dch', 'asc', 'dchxml'):
            intermediate = parse(serialize(doc, format=first, report=ConversionReport()), format=first)
            for second in ('dch', 'asc', 'dchxml'):
                with self.subTest(first=first, second=second):
                    loaded = parse(serialize(intermediate, format=second, report=ConversionReport()), format=second)
                    self.assertEqual(loaded.one('//Definition/Pattern/PossibleNames/PossibleName')['Name'], 'Alternate')
                    self.assertEqual(loaded.one('//Definition/Part/Component_CategoryTypes/CategoryType')['SubType'], 'Subtype')
                    self.assertEqual(loaded.one('/Schematic/ProjectLibs_Folders/Folder')['Path'], 'components')
                    self.assertEqual(loaded.one('/Schematic/ProjectLibs_Folders').arguments, ())

    def test_active_cache_links_have_named_managed_indices_and_independent_limit(self):
        doc, _ = sample()
        schematic = doc.one('/Schematic')
        first = schematic.one('CacheLib/Slots/Slot')
        second = schematic.one('CacheLib/Slots').append(first.clone())
        schematic['DesignCache_Count'] = 0
        links = schematic.one('DesignCache_Links')
        link = links.add('Link', 0)
        links.add('Link', 7)  # An inactive capacity value, not a live association.
        bind_schematic_references(doc)
        self.assertEqual(link['SlotIndex'], 0)
        with self.assertRaises(ValueError):
            link['SlotIndex'] = 1
        second.move_to(first.parent, 0)
        doc.rebuild()
        self.assertEqual(link['SlotIndex'], 1)
        self.assertEqual(links.children('Link')[1]['SlotIndex'], 7)
        self.assertEqual(schematic['DesignCache_Count'], 0)
        self.assertEqual(links.arguments, ())

    def test_unknown_row_kinds_still_fail_output(self):
        doc = new_schematic()
        doc.one('/Schematic/ProjectLibs_Folders').append(Element('Unexpected', 'value'))
        with self.assertRaises(ValueError):
            serialize(doc, format='asc', report=ConversionReport())
