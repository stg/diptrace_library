"""Local category identities and conservative sharing of XML public data."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import Element, ExportReport, new_schematic, parse
from lib.schematic.formats.dchxml.syntax import (set_attribute)
from lib.common.xml_catalog import CategoryCatalog, StyleTable


def category(name, type_name, subtype, foreign=99):
    result = Element('Category')
    set_attribute(result, 'Index', foreign)
    result.add('Name', name)
    row = result.add('CategoryTypes').add('CategoryType')
    set_attribute(row.add('Type', type_name), 'Index', foreign)
    if subtype:
        set_attribute(row.add('SubType', subtype), 'Index', foreign)
    return result


class XmlCatalogTests(unittest.TestCase):
    def test_asc_import_consumes_catalog_counts_before_shared_xml_projection(self):
        source = new_schematic()
        cache = source.one('/Schematic/CacheLib')
        cache.one('Categories').add('Category', 'Catalog', 4).add('Type', 'Kind', 7)
        cache.one('Subfolders').add('Folder', 'Folder')
        current = parse(source.to_asc_bytes(report=ExportReport()), format='asc')
        self.assertEqual(current.one('/Schematic/CacheLib/Categories').values, ())
        self.assertEqual(current.one('/Schematic/CacheLib/Subfolders').values, ())
        result = parse(current.to_dchxml_bytes(report=ExportReport()), format='dchxml')
        self.assertEqual(result.one('/Schematic/CacheLib/Categories/Category').values, ('Catalog', 4))

    def test_declared_unnamed_resources_and_nested_keys_remain_distinct(self):
        resources = Element('Categories')
        first = resources.add('Category', '', 4)
        first.add('Type', '', 7).add('Subtype', '', 11)
        first.add('Type', '', 9)
        resources.add('Category', '', 8)
        catalog = CategoryCatalog(key='Number')
        catalog.seed(resources)
        reference = category('', '', '')
        set_attribute(reference, 'Index', 4)
        set_attribute(reference.one('CategoryTypes/CategoryType/Type'), 'Index', 7)
        set_attribute(reference.one('CategoryTypes/CategoryType').add('SubType', ''), 'Index', 11)
        catalog.include(reference)
        self.assertEqual([r.scalar('Number') for r in catalog.element.children()], [4, 8])
        self.assertEqual([r.scalar('Number') for r in catalog.element.select('Category/Types/Type')], [7, 9])
        self.assertEqual(catalog.element.one('Category[1]/Types/Type[1]/SubTypes/SubType').scalar('Number'), 11)
        self.assertEqual(reference.one('CategoryTypes/CategoryType/SubType').scalar('Index'), 11)
        self.assertEqual([r.values for r in resources.children()], [('', 4), ('', 8)])

    def test_declared_keys_resolve_references_without_requiring_inline_labels(self):
        resources = Element('Categories')
        resources.add('Category', 'Known', 5).add('Type', 'Kind', 7).add('Subtype', 'Detail', 9)
        catalog = CategoryCatalog()
        catalog.seed(resources)
        reference = category('', '', '')
        set_attribute(reference, 'Index', 5)
        set_attribute(reference.one('CategoryTypes/CategoryType/Type'), 'Index', 7)
        set_attribute(reference.one('CategoryTypes/CategoryType').add('SubType', ''), 'Index', 9)
        catalog.include(reference)
        self.assertEqual(reference.scalar('Index'), 5)
        self.assertEqual(reference.one('CategoryTypes/CategoryType/Type').scalar('Index'), 7)
        self.assertEqual(len(catalog.element.children()), 1)

    def test_equal_labels_do_not_merge_declared_resource_identities(self):
        resources = Element('Categories')
        resources.add('Category', 'Same', 4)
        resources.add('Category', 'Same', 8)
        catalog = CategoryCatalog()
        catalog.seed(resources)
        reference = Element('Category')
        reference.add('Name', 'Same')
        set_attribute(reference, 'Index', 8)
        catalog.include(reference)
        self.assertEqual(reference.scalar('Index'), 8)
        self.assertEqual([r.scalar('Index') for r in catalog.element.children()], [4, 8])

    def test_unnamed_resources_survive_repeated_shared_xml_cycles(self):
        source = new_schematic()
        cache = source.one('/Schematic/CacheLib')
        cache.one('Categories').add('Category', '', 4).add('Type', '', 7).add('Subtype', '', 11)
        cache.add('PatternCategories').add('Category', '', 13).add('Type', '', 5).add('Subtype', '', 6)
        current = source
        for _ in range(3):
            current = parse(current.to_dchxml_bytes(report=ExportReport()), format='dchxml')
            cache = current.one('/Schematic/CacheLib')
            self.assertEqual(cache.one('Categories/Category').values, ('', 4))
            self.assertEqual(cache.one('Categories/Category/Type/Subtype').values, ('', 11))
            self.assertEqual(cache.one('PatternCategories/Category').values, ('', 13))
            self.assertEqual(cache.one('PatternCategories/Category/Type/Subtype').values, ('', 6))

    def test_edited_catalog_keys_are_validated_before_projection(self):
        for key in (True, '0', .5):
            resources = Element('Categories')
            resources.add('Category', '', key)
            with self.assertRaisesRegex(ValueError, 'integer key'):
                CategoryCatalog().seed(resources)
        resources = Element('Categories')
        resources.add('Category', 'First', 0)
        resources.add('Category', 'Second', 0)
        with self.assertRaisesRegex(ValueError, 'duplicate catalog'):
            CategoryCatalog().seed(resources)

    def test_category_keys_stay_typed_even_when_no_label_is_available(self):
        for value in (True, .5, '0'):
            catalog = CategoryCatalog()
            reference = Element('Category')
            set_attribute(reference, 'Index', value)
            with self.assertRaisesRegex(ValueError, 'integer values'):
                catalog.include(reference)

    def test_missing_category_key_does_not_create_or_bind_a_catalog_entry(self):
        catalog = CategoryCatalog(key='Number')
        missing = Element('Category')
        set_attribute(missing, 'Index', 0)
        named = category('Named', 'Type', '')
        catalog.reserve((missing, named))
        catalog.include(named)
        catalog.include(missing)
        self.assertEqual(missing.scalar('Index'), 0)
        self.assertEqual(named.scalar('Index'), 1)
        self.assertEqual([row.scalar('Number') for row in catalog.element.children()], [1])
        self.assertIsNone(missing.child('Name'))

    def test_missing_type_and_subtype_keys_keep_their_own_scopes(self):
        catalog = CategoryCatalog()
        missing_type = category('Logic', '', '')
        set_attribute(missing_type.one('CategoryTypes/CategoryType/Type'), 'Index', 0)
        missing_subtype = category('Logic', 'Buffer', '')
        set_attribute(missing_subtype.one('CategoryTypes/CategoryType').add('SubType', ''), 'Index', 0)
        named = category('Logic', 'Buffer', 'Single')
        catalog.reserve((missing_type, missing_subtype, named))
        for record in (named, missing_subtype, missing_type):
            catalog.include(record)
        self.assertEqual(missing_type.one('CategoryTypes/CategoryType/Type').scalar('Index'), 0)
        self.assertEqual(missing_subtype.one('CategoryTypes/CategoryType/SubType').scalar('Index'), 0)
        kind = catalog.element.one('Category/Types/Type')
        self.assertEqual(kind.scalar('Index'), 1)
        self.assertEqual(kind.one('SubTypes/SubType').scalar('Index'), 1)

    def test_late_missing_key_cannot_alias_an_already_allocated_resource(self):
        catalog = CategoryCatalog()
        catalog.include(category('Named', 'Type', ''))
        missing = Element('Category')
        set_attribute(missing, 'Index', 0)
        with self.assertRaisesRegex(ValueError, 'before catalog allocation'):
            catalog.include(missing)

    def test_shared_cycles_preserve_missing_classification_keys_without_false_names(self):
        from lib.schematic.model.objects import (new_symbol)
        from lib.schematic.model.refs import (bind_schematic_references)
        source = new_schematic()
        for name, category_name in (('Missing', ''), ('Known', 'Named')):
            part = source.one('/Schematic/Components').append(new_symbol('Device', name))
            pattern = part.one('Pattern')
            pattern.set_values(name)
            pattern.set_field('Pattern_CategoryName', category_name)
            pattern.set_field('Pattern_CategoryIndex', 0)
            if category_name:
                pattern.one('Pattern_CategoryTypes').add('Pattern_Type', 'Type', 'Subtype', 0, -1)
        bind_schematic_references(source)
        current = source
        for _ in range(3):
            xml = current.as_dchxml(report=ExportReport())
            catalog = xml.select('/Source/Library/Library/Categories/Category')
            self.assertEqual([row.scalar('Number') for row in catalog], [1])
            current = parse(xml.to_dchxml(), format='dchxml')
            missing, known = current.select('/Schematic/Components/Part/Pattern')
            self.assertEqual((missing.scalar('Pattern_CategoryName'), missing.scalar('Pattern_CategoryIndex')), ('', 0))
            self.assertEqual(known.scalar('Pattern_CategoryName'), 'Named')
            self.assertEqual(known.one('Pattern_CategoryTypes/CategoryType').values[:2], ('Type', 'Subtype'))
        original = source.select('/Schematic/Components/Part/Pattern')
        self.assertEqual([row.scalar('Pattern_CategoryIndex') for row in original], [0, 0])

    def test_pattern_catalog_uses_number_keys_and_reference_uses_index(self):
        catalog = CategoryCatalog(key='Number')
        reference = category('Passives', 'Capacitor', 'Chip')
        catalog.include(reference)
        self.assertEqual(reference.scalar('Index'), 0)
        entry = catalog.element.one('Category')
        self.assertEqual(entry.scalar('Number'), 0)
        self.assertIsNone(entry.child('Index'))
        self.assertEqual(entry.one('Types/Type').scalar('Number'), 0)
        self.assertEqual(entry.one('Types/Type/SubTypes/SubType').scalar('Number'), 0)

    def test_names_rebuild_local_category_type_and_subtype_indices(self):
        catalog = CategoryCatalog()
        records = [category('Logic', 'Buffer', 'Single'), category('Analog', 'Amplifier', ''),
                   category('Logic', 'Buffer', 'Multiple'), category('Logic', 'Buffer', 'Single', 12)]
        for item in records:
            catalog.include(item)
        self.assertEqual([r.scalar('Index') for r in records], [0, 1, 0, 0])
        subtypes = [r.select('CategoryTypes/CategoryType/SubType') for r in records]
        self.assertEqual([s[0].scalar('Index') if s else None for s in subtypes], [0, None, 1, 0])
        self.assertEqual(len(catalog.element.children('Category')), 2)
        self.assertEqual(len(catalog.element.select('Category/Types/Type/SubTypes/SubType')), 2)

    def test_style_sharing_ignores_attribute_order_and_only_its_generated_key(self):
        styles = StyleTable('PadStyles', 'PadStyle', 'Name', 'PadT')
        first = Element('PadStyle')
        set_attribute(first, 'Name', 'old')
        set_attribute(first, 'Type', 'Surface')
        set_attribute(first.add('MainStack'), 'Width', 1)
        other = Element('PadStyle')
        set_attribute(other, 'Type', 'Surface')
        set_attribute(other, 'Name', 'different old name')
        set_attribute(other.add('MainStack'), 'Width', 1.0)
        self.assertEqual(styles.include(first), 'PadT0')
        self.assertEqual(styles.include(other), 'PadT0')
        set_attribute(other.one('MainStack'), 'Width', 2)
        self.assertEqual(styles.include(other), 'PadT1')
        self.assertEqual(len(styles.element.children()), 2)


if __name__ == '__main__':
    unittest.main()
