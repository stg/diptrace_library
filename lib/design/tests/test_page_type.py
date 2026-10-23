"""PageType is the single current value behind redundant binary emissions."""
import unittest

from lib.design import new_schematic, parse, parse_dch


PAGE = '/Schematic/Pages/Page'


def integer(value):
    return (value+1000000).to_bytes(3, 'big')


class PageTypeTests(unittest.TestCase):
    def test_later_page_layout_overrides_a_contradictory_compatibility_prefix(self):
        source = new_schematic()
        source.one(PAGE).set_field('PageType', 1)
        data = source.to_dch_bytes()
        parsed = parse_dch(data)
        prefix = parsed.one(PAGE).source.end
        current = parsed.one(PAGE+'/PageType').source.start
        self.assertEqual(data[prefix:prefix+3], integer(1))
        self.assertEqual(data[current:current+3], integer(1))
        altered = data[:prefix]+integer(0)+data[prefix+3:]
        loaded = parse_dch(altered)
        self.assertEqual(loaded.one(PAGE).scalar('PageType'), 1)
        self.assertIsNone(loaded.one(PAGE).child('StoredData'))
        self.assertEqual(loaded.to_dch_bytes(), data)
        self.assertFalse(loaded.root.changed)

    def test_current_edit_drives_both_emissions_for_every_binary_output_version(self):
        source = new_schematic()
        page = source.one(PAGE)
        page.set_field('PageType', 1)
        for version in (46, 47, 48):
            with self.subTest(version=version):
                current = source.clone()
                for value in (0, 1, 0):
                    current.one(PAGE).set_field('PageType', value)
                    data = current.to_dch_bytes(version=version)
                    current = parse_dch(data)
                    loaded = current.one(PAGE)
                    self.assertEqual(loaded.scalar('PageType'), value)
                    for offset in (loaded.source.end, loaded.one('PageType').source.start):
                        self.assertEqual(data[offset:offset+3], integer(value))
                    self.assertEqual(current.to_dch_bytes(version=version), data)
        self.assertEqual(page.scalar('PageType'), 1)

    def test_all_inputs_share_one_editable_page_type_property(self):
        source = new_schematic()
        source.one(PAGE).set_field('PageType', 1)
        for incoming in ('dch', 'asc', 'dchxml'):
            with self.subTest(incoming=incoming):
                current = parse(getattr(source, 'to_'+incoming+'_bytes')(), format=incoming)
                self.assertEqual(current.one(PAGE).scalar('PageType'), 1)
                self.assertIsNone(current.one(PAGE).child('StoredData'))
                current.one(PAGE).set_field('PageType', 0)
                for outgoing in ('dch', 'asc', 'dchxml'):
                    loaded = parse(getattr(current, 'to_'+outgoing+'_bytes')(), format=outgoing)
                    self.assertEqual(loaded.one(PAGE).scalar('PageType'), 0)


if __name__ == '__main__':
    unittest.main()
