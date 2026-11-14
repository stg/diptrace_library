"""Logical component selections use their own library catalogue scope."""
import unittest

from lib.component.model import new_library, new_component, new_pattern
from lib.component.formats import io
from lib.tests.library_catalogue_contract import LibraryCatalogueContract


class ComponentCatalogueTests(LibraryCatalogueContract, unittest.TestCase):
    library = staticmethod(new_library)
    entry = staticmethod(new_component)
    io = io
    prefix = 'Component'
    collection = 'Components'
    formats = ('eli', 'asc', 'elixml')

    def test_shared_part_labels_select_the_component_category(self):
        document, owner, alpha, _, _, _ = self.example()
        owner.one('Parts/Part')['Component_CategoryName'] = 'Alpha'
        self.assertIs(alpha, owner['Category'])
        alpha['Name'] = 'Renamed'
        self.assertEqual('Renamed', owner.one('Parts/Part')['Component_CategoryName'])
        document.validate()

    def test_attached_physical_classifications_do_not_use_the_logical_catalogue(self):
        document, owner, alpha, _, _, _ = self.example()
        pattern = new_pattern('Physical')
        pattern['Pattern_CategoryName'] = 'Physical category'
        pattern['Pattern_CategoryIndex'] = 7
        row = pattern.one('Pattern_CategoryTypes').add('CategoryType', 'Physical type', '', 11, -1)
        owner.append(pattern)
        owner['Category'] = alpha
        alpha['Name'] = 'Renamed logical category'
        self.assertNotIn('Category', pattern.schema.fields)
        self.assertNotIn('TypeDefinition', row.schema.fields)
        self.assertEqual('Physical category', pattern['Pattern_CategoryName'])
        self.assertEqual('Physical type', row['Type'])
        document.validate()
