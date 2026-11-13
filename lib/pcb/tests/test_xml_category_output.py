"""PCB XML resolves resource labels without changing the source or library data."""
from copy import deepcopy
import unittest
from xml.etree import ElementTree

import lib
from lib.common.units import XmlUnits
from lib.pcb.formats.dipxml.library_output import project_library
from lib.pcb.formats.dipxml.versions import XmlVersion
from lib.pcb.tests.test_cache_projection import signature
from lib.pcb.tests.test_dipxml_library import CATEGORIES, source


def category_fixture():
    root = ElementTree.fromstring(source())
    physical = root.find('Library/Library')
    categories = ElementTree.fromstring(CATEGORIES)
    category = categories.find('Category')
    category.set('Number', category.attrib.pop('Index'))
    physical.insert(0, categories)
    selection = root.find('Library/Components/Component/Part/Category')
    physical.find('Patterns/Pattern').insert(0, deepcopy(selection))
    return ElementTree.tostring(root, encoding='utf-8')


class PcbCategoryLabelTests(unittest.TestCase):
    def test_index_only_selections_match_complete_named_library_plans(self):
        document = lib.parse(category_fixture(), report=lib.ConversionReport())
        board = document.one('/Board')
        slot = board.one('CacheLib/Slots/Slot')
        owners = ((slot.one('Definition/Part'), 'Component'),
                  (slot.one('Definition/Pattern'), 'Pattern'))
        placed = board.select('Components/Component/Pattern')
        profiles = tuple(lib.format_capabilities('dipxml', family='pcb').write_versions)

        def project(version, units):
            return project_library(board, units=XmlUnits(units), physical=placed,
                                   profile=XmlVersion.output(version), report=lib.ConversionReport())

        named = {(version, units): project(version, units).plan.key()
                 for version in profiles for units in ('mm', 'mil', 'inch')}
        for owner, prefix in owners:
            owner[prefix + '_CategoryName'] = ''
            for row in owner.select(prefix + '_CategoryTypes/CategoryType'):
                row.set_values('', '', *row.values[2:])
        document.validate()
        before = signature(document.root)

        for version, units in named:
            with self.subTest(version=version, units=units):
                result = project(version, units)
                symbol = result.plan.child('Components').children[0].children[0]
                category = symbol.child('Category')
                self.assertIsNotNone(category.child('Name'), 'Missing resolved category label for symbol')
                self.assertEqual(category.child('Name').arguments[0].value, 'Passives')
                row = category.child('CategoryTypes').children[0]
                self.assertEqual(row.child('Type').arguments[0].value, 'Function')
                self.assertEqual(row.child('SubType').arguments[0].value, 'General')
                self.assertTrue(result.plan.key() == named[version, units],
                                'Only redundant input labels differed; complete destination plans must agree')
        self.assertEqual(signature(document.root), before)


if __name__ == '__main__':
    unittest.main()
