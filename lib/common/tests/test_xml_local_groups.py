"""Public local group keys use Id or Number according to the library dialect."""
import unittest
from unittest.mock import patch

from lib.common.local_keys import map_key
from lib.common.model import Element
from lib.common.units import XmlUnits
from lib.common.xml import XmlDialect, loads
from lib.common.xml_library_values import read_groups
from lib.common.xml_records import XmlRecord


def groups(text):
    dialect = XmlDialect(number_attributes=frozenset(('Item', name) for name in ('Id', 'Number', 'X', 'Y')),
                         boolean_attributes=frozenset({('Item', 'Enabled')}))
    record = XmlRecord(loads('<Source><Groups>'+text+'</Groups></Source>', dialect=dialect).one('/Source'))
    owner = Element('Pattern')
    owner.add('Pattern_Groups')
    keys = read_groups(record, owner, units=XmlUnits('mm'), container='Pattern_Groups')
    record.finish()
    return keys, owner


class XmlLocalGroupTests(unittest.TestCase):
    def test_key_spellings_map_to_the_same_group_positions(self):
        for attributes in ('Id="31"', 'Number="31"', 'Id="31" Number="31"'):
            with self.subTest(attributes=attributes):
                keys, owner = groups('<Item '+attributes+' X="1" Y="2"/>')
                self.assertEqual(keys, {31: 0})
                self.assertEqual(owner.one('Pattern_Groups/pt').values, (True, 0, 3, -6))

    def test_conflicting_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'conflicting local group keys'):
            groups('<Item Id="3" Number="4"/>')

    def test_repeated_keys_across_spellings_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate group'):
            groups('<Item Id="3"/><Item Number="3"/>')

    def test_inactive_keys_clear_members_without_masking_missing_keys(self):
        with patch('lib.common.xml_library_values.import_notice') as notice:
            keys, owner = groups('<Item Id="7" Enabled="N" X="1" Y="2"/>'
                                 '<Item Id="31" Enabled="Y" X="3" Y="4"/><Item X="5" Y="6"/>')
        self.assertEqual(keys, {7: -1, 31: 0, 2: 1})
        self.assertEqual([row.values for row in owner.select('Pattern_Groups/pt')],
                         [(True, 0, 9, -12), (True, 1, 15, -18)])
        member = Element('Pad')
        self.assertEqual(map_key(member, 'Group', 7, keys), -1)
        self.assertIsNone(member.child('UnresolvedKeys'))
        self.assertEqual(map_key(member, 'Group', 31, keys), 0)
        self.assertEqual(map_key(member, 'Group', 99, keys), -1)
        self.assertEqual(member.one('UnresolvedKeys/Key').values, ('Group', 99))
        self.assertEqual(notice.call_args.args[:2], ('info', 'local-group-normalization'))

    def test_inactive_records_still_validate_their_data_and_keys(self):
        for text, message in (
                ('<Item Id="7" Enabled="N"/><Item Number="7"/>', 'duplicate group'),
                ('<Item Enabled="maybe"/>', 'boolean'),
                ('<Item Enabled="N" X="text"/>', 'numeric')):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, message):
                groups(text)


if __name__ == '__main__':
    unittest.main()
