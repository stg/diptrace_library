"""New PCB records must not claim an association with an existing schematic."""
import unittest

from lib.common.conversion import ConversionReport
from lib.pcb.formats import io
from lib.pcb.model.objects import new_component, new_document, new_pad


class PcbConstructorTests(unittest.TestCase):
    def test_created_components_remain_unlinked_in_every_format(self):
        document = new_document()
        for refdes in ('J1', 'J2'):
            component = document.one('/Board/Components').append(new_component('Connector', refdes))
            component.one('Pattern/Pads').append(new_pad('1'))
            self.assertEqual(component['HiddenId'], -1)
            self.assertFalse(component.select('HierarchyPath/Item'))
        for format in ('dip', 'asc', 'dipxml'):
            with self.subTest(format=format):
                rebuilt = io.parse(io.serialize(document, format=format, report=ConversionReport()),
                                   report=ConversionReport())
                components = rebuilt.select('/Board/Components/Component')
                self.assertEqual([component['HiddenId'] for component in components], [-1, -1])
                self.assertTrue(all(not component.select('HierarchyPath/Item') for component in components))
                rebuilt.validate()


if __name__ == '__main__':
    unittest.main()
