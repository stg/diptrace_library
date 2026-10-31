"""Plain footprint text fields share one schema across document owners."""
import unittest

from lib.common.footprint_objects import new_pattern
from lib.common.footprint_records import nested_definition
from lib.common.model import Element
from lib.common.user_fields import USER_FIELD, USER_FIELDS


class FootprintUserFieldTests(unittest.TestCase):
    def test_footprint_collections_and_members_have_common_plain_field_definitions(self):
        pattern = new_pattern('Example')
        collection = pattern.one('UserFields')
        field = collection.add('UserField', 'Rating', '10 V', 0)
        self.assertIs(nested_definition(collection), USER_FIELDS)
        self.assertIs(nested_definition(field), USER_FIELD)
        field.bind_schema(nested_definition(field))
        field['Value'] = '16 V'
        self.assertEqual(field.values, ('Rating', '16 V', 0))

    def test_component_and_symbol_label_scopes_remain_domain_owned(self):
        for kind in ('Component', 'Part'):
            owner = Element(kind)
            collection = owner.add('UserFields')
            field = collection.add('UserField', 'Rating', '10 V', 0)
            self.assertIsNone(nested_definition(collection))
            self.assertIsNone(nested_definition(field))


if __name__ == '__main__':
    unittest.main()
