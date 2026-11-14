"""Shared descriptions and independent part values edit through one owned tree."""
import unittest

from lib.component.model import new_library, new_component, new_part


class ComponentMetadataTests(unittest.TestCase):
    def make_document(self):
        document = new_library('Example library')
        component = document.one('/Library/Components').append(new_component('Example', 'U'))
        component.one('Parts').append(new_part('Gate B'))
        return document, component, component.select('Parts/Part')

    def test_empty_library_and_multiple_parts_validate(self):
        new_library().validate()
        document, component, parts = self.make_document()
        self.assertEqual('Example library', document.one('/Library')['Name'])
        self.assertEqual(['Example', 'Example'], [part['Name'] for part in parts])
        self.assertEqual(['U', 'U'], [part['RefDes'] for part in parts])
        document.validate()

    def test_part_and_component_access_edit_the_same_metadata(self):
        document, component, parts = self.make_document()
        parts[1]['Name'] = 'Renamed'
        parts[0].set('Manufacturer', 'Example maker')
        component['RefDes'] = 'X'
        component['Datasheet'] = 'https://example.invalid/device'
        for part in parts:
            self.assertEqual(('Renamed', 'X', 'Example maker', 'https://example.invalid/device'),
                tuple(part[name] for name in ('Name', 'RefDes', 'Manufacturer', 'Datasheet')))
            self.assertIsNone(part.child('Name'))
            self.assertIsNone(part.child('Manufacturer'))
        self.assertEqual('Renamed', component['Name'])
        document.validate()

    def test_value_part_name_and_simulation_remain_independent(self):
        document, _, parts = self.make_document()
        parts[0]['Value'] = 'First value'
        parts[1]['Value'] = 'Second value'
        parts[1]['PartName'] = 'Gate C'
        parts[0]['ModelString'] = 'ExampleA'
        parts[1]['ModelString'] = 'ExampleB'
        self.assertEqual(['First value', 'Second value'], [part['Value'] for part in parts])
        self.assertEqual(['ExampleA', 'ExampleB'], [part['ModelString'] for part in parts])
        self.assertEqual('Part 1', parts[0]['PartName'])
        document.validate()

    def test_clone_metadata_is_owned_by_the_clone(self):
        document, component, parts = self.make_document()
        clone = document.clone()
        clone_parts = clone.select('/Library/Components/Component/Parts/Part')
        clone_parts[1]['Name'] = 'Clone'
        self.assertEqual(['Clone', 'Clone'], [part['Name'] for part in clone_parts])
        self.assertEqual(['Example', 'Example'], [part['Name'] for part in parts])
        self.assertEqual('Example', component['Name'])
        clone.validate()

    def test_moving_a_part_changes_its_owner_without_copying_descriptions(self):
        document, first, parts = self.make_document()
        second = document.one('/Library/Components').append(new_component('Second', 'R'))
        parts[1]['Value'] = 'Retained value'
        parts[1].move_to(second.one('Parts'))
        self.assertEqual(('Second', 'R', 'Retained value'),
                         (parts[1]['Name'], parts[1]['RefDes'], parts[1]['Value']))
        parts[1]['Manufacturer'] = 'Second maker'
        self.assertEqual('', first['Manufacturer'])
        self.assertEqual('Second maker', second['Manufacturer'])
        document.validate()

    def test_invalid_metadata_and_removing_the_last_part_are_atomic(self):
        document = new_library()
        component = document.one('/Library/Components').append(new_component('Example', 'U'))
        part = component.one('Parts/Part')
        with self.assertRaises(TypeError):
            part['RefDes'] = 7
        self.assertEqual('U', component['RefDes'])
        with self.assertRaises(ValueError):
            part.detach()
        self.assertIs(component.one('Parts'), part.parent)
        document.validate()

    def test_an_unattached_part_does_not_invent_an_independent_component_name(self):
        part = new_part('Gate A')
        self.assertEqual('', part['Name'])
        with self.assertRaisesRegex(ValueError, 'attach the part'):
            part['Name'] = 'Unowned'

    def test_searches_observe_component_metadata_edits_through_every_part(self):
        document, component, parts = self.make_document()
        selector = '/Library/Components/Component/Parts/Part[Name="Example"]'
        self.assertEqual(parts, document.select(selector))
        component['Name'] = 'Renamed'
        self.assertEqual([], document.select(selector))
        self.assertEqual(parts, document.select(selector.replace('Example', 'Renamed')))

    def test_low_level_field_insertion_cannot_create_a_stored_duplicate(self):
        document, component, parts = self.make_document()
        for name in ('Name', 'RefDes', 'Manufacturer'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                parts[1].add(name, 'Independent duplicate')
            self.assertIsNone(parts[1].child(name))
        self.assertEqual('Example', component['Name'])
        document.validate()


if __name__ == '__main__':
    unittest.main()
