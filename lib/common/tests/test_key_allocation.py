"""Generated export keys respect authored and unresolved identities."""
import unittest

from lib.common.key_allocation import allocate_keys
from lib.common.model import Element


class KeyAllocationTests(unittest.TestCase):
    def test_later_declared_key_cannot_be_taken_by_an_earlier_unkeyed_record(self):
        first,second,third = Element('Pad'),Element('Pad'),Element('Pad')
        second.add('Id',1)
        before = tuple(tuple(node.children()) for node in (first,second,third))
        keys = allocate_keys((first,second,third))
        self.assertEqual((keys[first],keys[second],keys[third]),(2,1,3))
        self.assertEqual(tuple(tuple(node.children()) for node in (first,second,third)),before)

    def test_unresolved_keys_are_reserved_and_duplicate_declared_keys_fail(self):
        first,second = Element('Pad'),Element('Pad')
        keys = allocate_keys((first,second),reserved=(1,2))
        self.assertEqual((keys[first],keys[second]),(3,4))
        first.add('Id',1)
        with self.assertRaises(ValueError):
            allocate_keys((first,second),reserved=(1,))
        second.add('Id',1)
        with self.assertRaises(ValueError):
            allocate_keys((first,second))

    def test_invalid_key_values_are_rejected(self):
        for value in (-1,True,1.5,'1'):
            with self.subTest(value=value):
                node = Element('Pad')
                node.add('Id',value)
                with self.assertRaises(ValueError):
                    allocate_keys((node,))


if __name__ == '__main__':
    unittest.main()
